import asyncio
import contextlib
import json
import os
import sqlite3
import subprocess
import time
import uuid
from pathlib import Path

from fastapi import HTTPException
from .models import Config
from .process_tree import ProcessTree

CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
AUDIO_EXTENSIONS = {'.wav', '.mp3', '.flac', '.ogg', '.m4a', '.aac', '.opus', '.aiff', '.wma'}

@contextlib.contextmanager
def connect(path):
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL')
    try:
        with db:
            yield db
    finally:
        db.close()

def inside(path, root):
    try:
        return Path(path).resolve().is_relative_to(Path(root).resolve())
    except (OSError, ValueError):
        return False

class Manager:
    def __init__(self, home: Path):
        self.home = home.resolve()
        self.home.mkdir(parents=True, exist_ok=True)
        self.config_path = self.home / 'config.json'
        if self.config_path.exists():
            previous = json.loads(self.config_path.read_text('utf-8'))
            self.config = Config.model_validate(previous)
            for service in ('tts', 'vc', 'auk'):
                if service not in previous:
                    getattr(self.config, service).output_dir = str(self.home / service)
                    self.save(self.config)
            if 'sfx' not in previous:
                self.config.sfx.output_dir = str(self.home / 'sfx')
                self.save(self.config)
            if 'separation' not in previous:
                self.config.separation.output_dir = str(self.home / 'separation')
                self.save(self.config)
        else:
            self.config = Config()
            self.config.auk.output_dir = str(self.home / 'auk')
            self.config.tts.output_dir = str(self.home / 'tts')
            self.config.vc.output_dir = str(self.home / 'vc')
            self.config.sfx.output_dir = str(self.home / 'sfx')
            self.config.music.output_dir = str(self.home / 'music')
            self.config.denoise.output_dir = str(self.home / 'denoise')
            self.config.separation.output_dir = str(self.home / 'separation')
            self.config.library.database = str(self.home / 'library.sqlite3')
            self.save(self.config)
        self.active = self.config.model_copy(deep=True)
        self.states = {}
        self.queue = asyncio.Queue(maxsize=32)
        self.process = None
        self.current = None
        self.worker_task = None
        self.scan_lock = asyncio.Lock()
        self.control_lock = asyncio.Lock()
        self.db_path = self.home / 'jobs.sqlite3'
        with connect(self.db_path) as db:
            db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, service TEXT, status TEXT, created REAL, updated REAL, request TEXT, result TEXT, error TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS music_trash (job_id TEXT PRIMARY KEY, directory TEXT NOT NULL, trashed_at REAL NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS music_metadata (job_id TEXT, song_index INTEGER, title TEXT, group_name TEXT, PRIMARY KEY(job_id,song_index))')
            db.execute('CREATE TABLE IF NOT EXISTS music_workspaces (name TEXT PRIMARY KEY, created REAL NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS music_playbacks (job_id TEXT, song_index INTEGER, played_at REAL NOT NULL, PRIMARY KEY(job_id,song_index))')
            db.execute('CREATE TABLE IF NOT EXISTS music_annotations (job_id TEXT, song_index INTEGER, rating INTEGER NOT NULL DEFAULT 0, favorite INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(job_id,song_index))')
            db.execute("INSERT OR IGNORE INTO music_workspaces SELECT DISTINCT group_name, ? FROM music_metadata WHERE group_name != ''", (time.time(),))
            db.execute("UPDATE jobs SET status='failed', error='程序退出，任务已中断；请重新提交' WHERE status IN ('queued','running')")

    def save(self, config):
        temp = self.config_path.with_suffix('.tmp')
        temp.write_text(config.model_dump_json(indent=2), 'utf-8')
        temp.replace(self.config_path)
        self.config = config

    def log(self, message):
        with (self.home / 'service.log').open('a', encoding='utf-8') as out:
            out.write(f'{time.strftime("%Y-%m-%d %H:%M:%S")} {message}\n')

    async def start(self):
        for name in ('music', 'denoise', 'separation', 'sfx', 'tts', 'vc', 'auk', 'library'):
            await self.restart(name)
        self.worker_task = asyncio.create_task(self.work())

    async def close(self):
        if self.worker_task:
            self.worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.worker_task
        if self.process and self.process.returncode is None:
            self.process.kill()
            await self.process.wait()

    async def restart(self, name):
        if name not in ('music', 'denoise', 'separation', 'sfx', 'tts', 'vc', 'auk', 'library'):
            raise HTTPException(404, '服务不存在')
        async with self.control_lock:
            if any(j['service'] == name and j['status'] in ('queued', 'running') for j in self.jobs()):
                raise HTTPException(409, '该服务仍有任务，请等待或取消后重启')
            if name == 'library' and self.scan_lock.locked():
                raise HTTPException(409, '正在扫描，请稍后重启')
            cfg = getattr(self.config, name).model_copy(deep=True)
            setattr(self.active, name, cfg)
            self.states[name] = {'status': 'checking', 'message': '正在检查配置'}
            issues = []
            if not cfg.enabled:
                self.states[name] = {'status': 'stopped', 'message': '服务已停用'}
                return self.states[name]
            try:
                if name == 'library':
                    if not cfg.directory or not Path(cfg.directory).is_dir():
                        issues.append('请选择存在的音效目录')
                    if not cfg.database:
                        issues.append('请配置 SQLite 数据库路径')
                    else:
                        Path(cfg.database).parent.mkdir(parents=True, exist_ok=True)
                        with connect(cfg.database) as db:
                            db.execute('CREATE TABLE IF NOT EXISTS sounds (id TEXT PRIMARY KEY, root TEXT, path TEXT, name TEXT, category TEXT, size INTEGER, modified REAL, UNIQUE(root,path))')
                else:
                    if not Path(cfg.python).is_file():
                        issues.append('Python 解释器不存在')
                    if not cfg.output_dir:
                        issues.append('请配置输出目录')
                    else:
                        Path(cfg.output_dir).mkdir(parents=True, exist_ok=True)
                    if name == 'music':
                        if not Path(cfg.model_path).is_file():
                            issues.append('YuE2 权重文件不存在')
                        if not (Path(cfg.runtime_dir) / 'comfy_extras' / 'nodes_yue2.py').is_file():
                            issues.append('运行目录缺少 YuE2 支持，请使用新版 ComfyUI 运行代码')
                    elif name == 'auk':
                        from .auk_worker import check_models
                        issues.extend(check_models(cfg.model_dump()))
                    elif name in ('tts', 'vc'):
                        from .voice_validation import check_models
                        issues.extend(check_models(name, cfg.model_dump()))
                    elif name == 'sfx':
                        root = Path(cfg.model_dir)
                        required = ['model_index.json', 'transformer', 'vae', 'text_encoder', 'tokenizer', 'scheduler']
                        if not cfg.model_dir or any(not (root / item).exists() for item in required):
                            issues.append('需要完整的 MOSS-SoundEffect v2.0 模型目录（含文本编码器和 VAE）')
                        else:
                            required_files = ['transformer/config.json', 'transformer/diffusion_pytorch_model.safetensors',
                                'scheduler/scheduler_config.json', 'text_encoder/config.json',
                                'tokenizer/tokenizer.json', 'tokenizer/tokenizer_config.json']
                            index = root / 'text_encoder/model.safetensors.index.json'
                            if index.is_file():
                                shards = set(json.loads(index.read_text('utf-8'))['weight_map'].values())
                                required_files += ['text_encoder/' + shard for shard in shards]
                            else:
                                required_files += ['text_encoder/model.safetensors']
                            if any(not inside(root / item, root) or not (root / item).is_file() for item in required_files):
                                issues.append('MOSS-SoundEffect 模型文件不完整，请完成下载')
                            if not any((root / 'vae' / item).is_file() for item in ('vae_128d_48k.pth', 'diffusion_pytorch_model.safetensors')):
                                issues.append('缺少 MOSS-SoundEffect 音频解码器权重')
                    else:
                        marker = Path(cfg.model_dir) / 'last_best_checkpoint'
                        if not cfg.model_dir or not marker.is_file():
                            issues.append('模型目录缺少 last_best_checkpoint 和配套权重')
                        else:
                            checkpoint = marker.read_text('utf-8').strip().splitlines()[0]
                            if not inside(Path(cfg.model_dir) / checkpoint, cfg.model_dir) or not (Path(cfg.model_dir) / checkpoint).is_file():
                                issues.append('last_best_checkpoint 指向的权重不存在或越界')
                    if not issues:
                        probe = await asyncio.create_subprocess_exec(cfg.python, str(Path(__file__).with_name('worker.py')), '--probe', name, json.dumps(cfg.model_dump()), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, creationflags=CREATE_NO_WINDOW)
                        try:
                            out, err = await asyncio.wait_for(probe.communicate(), 45)
                        except asyncio.TimeoutError:
                            probe.kill()
                            await probe.wait()
                            issues.append('运行环境检查超时')
                        else:
                            if probe.returncode:
                                issues.append((err or out).decode('utf-8', errors='replace')[-2000:])
            except Exception as error:
                issues.append(str(error))
            self.states[name] = {'status': 'needs_config' if issues else 'ready', 'message': '；'.join(issues) if issues else '就绪 · 按需运行'}
            self.log(f'{name}: {self.states[name]["message"]}')
            return self.states[name]

    def status(self):
        return {name: {**state, 'pending_restart': getattr(self.config, name) != getattr(self.active, name), 'busy': bool(self.current and self.current['service'] == name)} for name, state in self.states.items()}

    def require(self, name):
        if self.states.get(name, {}).get('status') != 'ready':
            raise HTTPException(503, self.states.get(name, {}).get('message', '服务尚未就绪'))

    def jobs(self):
        with connect(self.db_path) as db:
            rows = db.execute('SELECT * FROM jobs WHERE id NOT IN (SELECT job_id FROM music_trash) ORDER BY created DESC LIMIT 200').fetchall()
        return [self.job_dict(row) for row in rows]

    def job_dict(self, row):
        obj = dict(row)
        obj['request'] = json.loads(obj['request'])
        obj['result'] = json.loads(obj['result']) if obj['result'] else None
        if obj['service'] == 'music':
            with connect(self.db_path) as db:
                metadata = db.execute('SELECT song_index,title,group_name FROM music_metadata WHERE job_id=?', (obj['id'],)).fetchall()
                obj['played_indices'] = [r['song_index'] for r in db.execute('SELECT song_index FROM music_playbacks WHERE job_id=?', (obj['id'],))]
                obj['song_annotations'] = {str(r['song_index']): {'rating': r['rating'], 'favorite': bool(r['favorite'])} for r in db.execute('SELECT song_index,rating,favorite FROM music_annotations WHERE job_id=?', (obj['id'],))}
            obj['song_metadata'] = {str(m['song_index']): {'title':m['title'], 'group':m['group_name']} for m in metadata}
            for m in metadata:
                result = obj['result'] or {}
                files = result.get('files', [])
                if m['song_index'] < len(files):
                    files[m['song_index']]['title'] = m['title']
                for score in result.get('scores', []):
                    if score['audio_index'] == m['song_index']:
                        score['title'] = m['title']
        return obj

    def annotate_music(self, job_id, index, rating, favorite):
        job = self.job(job_id)
        files = (job['result'] or {}).get('files', [])
        if job['service'] != 'music' or job['status'] != 'succeeded' or index < 0 or index >= len(files):
            raise HTTPException(404, '歌曲不存在或尚未完成')
        with connect(self.db_path) as db:
            db.execute('INSERT INTO music_annotations VALUES (?,?,?,?) ON CONFLICT(job_id,song_index) DO UPDATE SET rating=excluded.rating,favorite=excluded.favorite', (job_id, index, rating, int(favorite)))
        return {'rating': rating, 'favorite': favorite}

    def mark_music_played(self, job_id, index):
        job = self.job(job_id)
        files = (job['result'] or {}).get('files', [])
        if job['service'] != 'music' or job['status'] != 'succeeded' or index < 0 or index >= len(files):
            raise HTTPException(404, '歌曲不存在或尚未完成')
        with connect(self.db_path) as db:
            db.execute('INSERT OR IGNORE INTO music_playbacks VALUES (?,?,?)', (job_id, index, time.time()))
        return {'played_indices': self.job(job_id)['played_indices']}

    def music_workspaces(self):
        with connect(self.db_path) as db:
            return [row['name'] for row in db.execute('SELECT name FROM music_workspaces ORDER BY created, name')]

    def create_music_workspace(self, name):
        name = name.strip()
        if not name or len(name) > 60:
            raise HTTPException(422, '工作区名称需为 1–60 个字符')
        with connect(self.db_path) as db:
            if db.execute('SELECT 1 FROM music_workspaces WHERE name=?', (name,)).fetchone():
                raise HTTPException(409, '工作区已存在')
            db.execute('INSERT INTO music_workspaces VALUES (?,?)', (name, time.time()))
        return {'name': name}

    def edit_song(self, job_id, index, title, group):
        job = self.job(job_id)
        count = len((job['result'] or {}).get('files', [])) or job['request'].get('count') or 1
        if job['service'] != 'music' or index < 0 or index >= count:
            raise HTTPException(404, '歌曲不存在')
        with connect(self.db_path) as db:
            db.execute('INSERT INTO music_metadata VALUES (?,?,?,?) ON CONFLICT(job_id,song_index) DO UPDATE SET title=excluded.title,group_name=excluded.group_name', (job_id,index,title,group))
            if group:
                db.execute('INSERT OR IGNORE INTO music_workspaces VALUES (?,?)', (group, time.time()))
        return self.job(job_id)

    async def trash_music_job(self, job_id):
        from .recycle import recycle_directory
        async with self.control_lock:
            job = self.job(job_id)
            if job['service'] != 'music' or job['status'] not in ('succeeded', 'failed', 'cancelled'):
                raise HTTPException(409, '请等待生成任务结束后再删除')
            # Only a direct task directory under a configured music output root is eligible.
            if len(job_id) != 32 or any(c not in '0123456789abcdef' for c in job_id):
                raise HTTPException(409, '生成目录标识无效')
            roots = {Path(self.active.music.output_dir).resolve(), Path(self.config.music.output_dir).resolve()}
            candidates = [root / job_id for root in roots if (root / job_id).is_dir()]
            if len(candidates) != 1:
                raise HTTPException(409, '找不到唯一的生成目录，请检查歌曲输出目录配置')
            directory = candidates[0]
            if directory.is_symlink() or directory.is_junction() or directory.resolve().parent not in roots:
                raise HTTPException(409, '生成目录路径无效')
            for entry in (job['result'] or {}).get('files', []) + (job['result'] or {}).get('scores', []):
                if not inside(entry['path'], directory):
                    raise HTTPException(409, '生成文件与目录不匹配')
            with connect(self.db_path) as db:
                pending = db.execute("SELECT request FROM jobs WHERE status IN ('queued','running')").fetchall()
            for row in pending:
                request = json.loads(row['request'])
                if request.get('source_job_id') == job_id or any(request.get(key) and inside(request[key], directory) for key in ('reference_audio_path', 'input_path')):
                    raise HTTPException(409, '其他任务正在使用此目录，请等待任务结束后再删除')
            try:
                await asyncio.to_thread(recycle_directory, directory)
            except Exception as error:
                raise HTTPException(409, f'无法移入回收站：{error}') from error
            with connect(self.db_path) as db:
                db.execute('INSERT INTO music_trash VALUES (?,?,?)', (job_id, str(directory), time.time()))
            return {'job_id': job_id, 'trashed': True}

    def job(self, job_id):
        with connect(self.db_path) as db:
            row = db.execute('SELECT * FROM jobs WHERE id=? AND id NOT IN (SELECT job_id FROM music_trash)', (job_id,)).fetchone()
        if not row:
            raise HTTPException(404, '任务不存在')
        return self.job_dict(row)

    def update(self, job_id, status, result=None, error=None):
        with connect(self.db_path) as db:
            db.execute('UPDATE jobs SET status=?,updated=?,result=?,error=? WHERE id=?', (status, time.time(), json.dumps(result) if result is not None else None, error, job_id))

    async def submit(self, name, request):
        async with self.control_lock:
            if name == 'music' and request.get('operation') == 'separate':
                # One in-flight separation per original track, including rapid double-clicks.
                for job in self.jobs():
                    if job['status'] in ('queued', 'running') and job['request'].get('operation') == 'separate' and job['request'].get('source_job_id') == request['source_job_id'] and job['request'].get('source_audio_index') == request['source_audio_index']:
                        return job
            breeze = name == 'tts' and request.get('model') == 'breeze-tts2'
            if breeze:
                from .breeze_worker import check_breeze
                issues = check_breeze(self.active.tts.model_dump())
                if not self.active.tts.enabled or issues:
                    raise HTTPException(503, '；'.join(issues) or '文字转语音服务已停用')
            else:
                self.require(name)
            if self.queue.full():
                raise HTTPException(429, '任务队列已满（32），请稍后重试')
            job_id = uuid.uuid4().hex
            cfg = getattr(self.active, name).model_dump()
            if breeze:
                cfg['output_dir'] = cfg['breeze_output_dir']
                cfg['device'] = 'cuda'
                request['cfg_scale'] = request.get('cfg_scale') or cfg['breeze_cfg_scale']
            if name == 'auk':
                for key in ('steps', 'cfg'):
                    if request.get(key) is None:
                        request[key] = cfg[key]
            if name in ('tts', 'vc') and not breeze:
                keys = ('language', 'temperature', 'max_new_tokens') if name == 'tts' else ('diffusion_steps', 'inference_cfg_rate', 'length_adjust')
                for key in keys:
                    if request.get(key) is None:
                        request[key] = cfg[key]
                if name == 'tts' and not request.get('reference_upload_id'):
                    request['speaker'] = request.get('speaker') or cfg['speaker']
            if name == 'sfx':
                for key in ('seconds', 'num_inference_steps', 'cfg_scale', 'sigma_shift'):
                    if request.get(key) is None:
                        request[key] = cfg[key]
                request['count'] = request.get('count') or cfg['default_count']
            if name == 'music' and request.get('operation') != 'separate':
                from .music_names import song_titles
                for key in ('steps', 'cfg', 'max_duration'):
                    if request.get(key) is None:
                        request[key] = cfg[key]
                request['count'] = request.get('count') or cfg['default_count']
                request['song_titles'] = song_titles(request.get('title', ''), request['count'])
            with connect(self.db_path) as db:
                db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,NULL,NULL)', (job_id, name, 'queued', time.time(), time.time(), json.dumps(request)))
                if name == 'music' and request.get('operation') != 'separate' and request.get('workspace'):
                    group = request['workspace']
                    db.execute('INSERT OR IGNORE INTO music_workspaces VALUES (?,?)', (group, time.time()))
                    for index, title in enumerate(request['song_titles']):
                        db.execute('INSERT INTO music_metadata VALUES (?,?,?,?)', (job_id, index, title, group))
            self.queue.put_nowait((job_id, name, request, cfg))
            self.log(f'{name} 任务已排队 {job_id}')
            return self.job(job_id)

    async def cancel(self, job_id):
        job = self.job(job_id)
        if job['status'] not in ('queued', 'running'):
            raise HTTPException(409, '任务已经结束')
        self.update(job_id, 'cancelled', error='用户取消')
        if self.current and self.current['id'] == job_id and self.process and self.process.returncode is None:
            self.process.kill()
            await self.process.wait()
        return self.job(job_id)

    async def work(self):
        while True:
            job_id, name, request, cfg = await self.queue.get()
            tree = None
            try:
                if self.job(job_id)['status'] == 'cancelled':
                    continue
                self.current = {'id': job_id, 'service': name}
                self.update(job_id, 'running')
                workdir = Path(cfg['output_dir']) / job_id
                workdir.mkdir(parents=True, exist_ok=True)
                payload = workdir / 'request.json'
                payload.write_text(json.dumps({'service': name, 'config': cfg, 'request': request, 'output': str(workdir)}, ensure_ascii=False), 'utf-8')
                with (workdir / 'worker.log').open('wb') as log:
                    env = {**os.environ, 'PYTHONUTF8':'1', 'PYTHONUNBUFFERED':'1'}
                    self.process = await asyncio.create_subprocess_exec(cfg['python'], str(Path(__file__).with_name('worker.py')), str(payload), stdout=log, stderr=log, creationflags=CREATE_NO_WINDOW, env=env)
                    tree = ProcessTree(self.process.pid)
                    if self.job(job_id)['status'] == 'cancelled':
                        self.process.kill()
                    await asyncio.wait_for(self.process.wait(), cfg['timeout_seconds'])
                if self.job(job_id)['status'] == 'cancelled':
                    continue
                if self.process.returncode:
                    raise RuntimeError((workdir / 'worker.log').read_text('utf-8', errors='replace')[-6000:])
                result = json.loads((workdir / 'result.json').read_text('utf-8'))
                if name == 'music' and request.get('operation') == 'transcribe':
                    if not result.get('scores'):
                        raise RuntimeError('推理进程没有返回曲谱')
                elif not result.get('files'):
                    raise RuntimeError('推理进程没有返回音频')
                for idx, file in enumerate(result['files']):
                    if not inside(file['path'], workdir) or not Path(file['path']).is_file():
                        raise RuntimeError('推理结果路径无效')
                    file['url'] = f'/v1/jobs/{job_id}/files/{idx}'
                for idx, score in enumerate(result.get('scores', [])):
                    path = Path(score['path'])
                    if not inside(path, workdir) or not path.is_file() or path.suffix != '.abc' or path.stat().st_size > 1024 * 1024:
                        raise RuntimeError('曲谱结果路径或大小无效')
                    score['url'] = f'/v1/jobs/{job_id}/scores/{idx}'
                self.update(job_id, 'succeeded', result=result)
                self.log(f'{name} 任务完成 {job_id}')
            except asyncio.CancelledError:
                if self.process and self.process.returncode is None:
                    self.process.kill()
                    await self.process.wait()
                self.update(job_id, 'failed', error='服务关闭，任务中断')
                raise
            except Exception as error:
                if self.process and self.process.returncode is None:
                    self.process.kill()
                    await self.process.wait()
                if self.job(job_id)['status'] != 'cancelled':
                    self.update(job_id, 'failed', error=str(error) or '推理超时，进程已释放')
                self.log(f'{name} 任务失败 {job_id}: {error}')
            finally:
                if tree:
                    tree.close()
                self.current = None
                self.process = None
                self.queue.task_done()

    def scan_sync(self):
        cfg = self.active.library
        root = Path(cfg.directory).resolve(strict=True)
        entries = []
        for directory, dirs, files in os.walk(root, followlinks=False, onerror=lambda e: (_ for _ in ()).throw(e)):
            dirs[:] = [d for d in dirs if not Path(directory, d).is_symlink() and inside(Path(directory, d), root)]
            for name in files:
                path = Path(directory, name)
                if path.suffix.lower() not in AUDIO_EXTENSIONS or not inside(path, root):
                    continue
                relative = path.relative_to(root)
                category = str(relative.parent).replace('\\', '/') if relative.parent != Path('.') else '未分类'
                stat = path.stat()
                sound_id = uuid.uuid5(uuid.NAMESPACE_URL, str(path.resolve())).hex
                entries.append((sound_id, str(root), str(relative), name, category, stat.st_size, stat.st_mtime))
        with connect(cfg.database) as db:
            db.execute('DELETE FROM sounds WHERE root=?', (str(root),))
            db.executemany('INSERT INTO sounds VALUES (?,?,?,?,?,?,?)', entries)
        self.log(f'音效扫描完成：{len(entries)} 个文件')
        return {'count': len(entries)}

    def sounds(self, category='', q='', limit=50, offset=0):
        self.require('library')
        root = str(Path(self.active.library.directory).resolve())
        where = 'root=? AND (?="" OR category=?) AND instr(lower(name),lower(?))>0'
        args = (root, category, category, q)
        with connect(self.active.library.database) as db:
            total = db.execute(f'SELECT count(*) FROM sounds WHERE {where}', args).fetchone()[0]
            rows = db.execute(f'SELECT * FROM sounds WHERE {where} ORDER BY name LIMIT ? OFFSET ?', (*args, limit, offset)).fetchall()
        return {'total': total, 'items': [{**dict(row), 'url': f'/v1/sounds/{row["id"]}/audio'} for row in rows]}

    def sound_path(self, sound_id):
        self.require('library')
        root = Path(self.active.library.directory).resolve()
        with connect(self.active.library.database) as db:
            row = db.execute('SELECT path FROM sounds WHERE id=? AND root=?', (sound_id, str(root))).fetchone()
        if not row:
            raise HTTPException(404, '音效不存在')
        path = root / row['path']
        if not inside(path, root) or not path.is_file():
            raise HTTPException(404, '文件不存在或已移出音效目录')
        return path
