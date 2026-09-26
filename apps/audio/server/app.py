import asyncio
import re
import threading
import base64
import subprocess
import tempfile
from typing import Literal
import contextlib
import os
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Depends, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .core import Manager, connect, inside
from .models import Config, AukRequest, ScoreEditRequest, MusicVariationRequest, MusicRequest, DenoiseRequest, SeparationRequest, SfxRequest, TtsRequest, VcRequest
from .voices import VOICES, VOICE_IDS
from .models import MusicTranscribeRequest, MusicAudioReferenceRequest, MusicSeparateRequest, MusicUploadSeparateRequest, ROOT
from .breeze_download import BreezeDownload
from .breeze_worker import check_breeze

def create_app(home: Path | None = None, token: str | None = None):
    home = home or Path(os.environ.get('LOCAL_AI_DATA', str(Path(__file__).resolve().parents[1] / 'data')))
    manager = Manager(home)
    breeze_download = BreezeDownload(ROOT / "runtimes/models/Breeze-TTS-2")
    token_path = home / 'api-token'
    if token is None:
        if not token_path.exists():
            token_path.write_text(secrets.token_urlsafe(32), 'utf-8')
        token = token_path.read_text('utf-8').strip()

    @asynccontextmanager
    async def lifespan(app):
        await manager.start()
        yield
        breeze_download.cancelled.set()
        await manager.close()

    app = FastAPI(title='Local AI Service', version='0.1.0', lifespan=lifespan, description='本地音频 AI 服务。所有业务接口使用 Bearer API Key；模型按任务加载并释放。')
    app.state.manager = manager
    app.add_middleware(CORSMiddleware, allow_origins=['http://127.0.0.1:1420', 'http://localhost:1420', 'http://tauri.localhost', 'https://tauri.localhost', 'tauri://localhost'], allow_methods=['GET', 'POST', 'PUT', 'DELETE'], allow_headers=['Authorization', 'Content-Type', 'X-Desktop-Key'])
    bearer = HTTPBearer(auto_error=False)

    def auth(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        if not credentials or not secrets.compare_digest(credentials.credentials, token):
            raise HTTPException(401, '需要有效的 Bearer API Key')

    secured = [Depends(auth)]
    desktop_key = secrets.token_urlsafe(32) if os.environ.get('LOCAL_AI_DESKTOP') == '1' else None
    if desktop_key:
        (home / 'desktop-token').write_text(desktop_key, 'utf-8')

    def desktop_auth(x_desktop_key: str = Header(default='')):
        if not desktop_key:
            raise HTTPException(403, '此功能仅限桌面应用使用')
        if not secrets.compare_digest(x_desktop_key, desktop_key):
            raise HTTPException(403, '桌面连接已失效，请重新连接或重启应用')

    @app.delete('/internal/music/jobs/{job_id}', dependencies=[Depends(desktop_auth)], include_in_schema=False)
    async def trash_music_job(job_id: str):
        result = await manager.trash_music_job(job_id)
        with playback_lock:
            for ticket, (path, _) in list(playback_tickets.items()):
                if not path.is_file():
                    playback_tickets.pop(ticket, None)
        return result

    @app.post('/internal/music/regenerate', dependencies=[Depends(desktop_auth)], include_in_schema=False)
    async def regenerate_score(edit: ScoreEditRequest):
        from .music_lora import prepare_loras
        original = manager.job(edit.job_id)
        scores = (original['result'] or {}).get('scores', [])
        if original['service'] != 'music' or original['status'] != 'succeeded' or edit.score_index >= len(scores):
            raise HTTPException(404, '原曲谱不存在')
        score = scores[edit.score_index]
        params = {key:value for key,value in original['request'].items() if key in MusicRequest.model_fields}
        params.update(count=1, seed=min(int(params.get('seed',42))+score['audio_index'], 2**32-2), mode=score['mode'], generate_score=True, planner_lora=None)
        params['workspace'] = edit.workspace.strip()
        if not params.get('acoustic_lora'):
            params['lora_provider'] = 'none'
        params = MusicRequest(**params).model_dump()
        params = prepare_loras(manager.active.music.lora_dir, params)
        params['abc'] = edit.abc
        return await response_for(await manager.submit('music', params), False)


    @app.post('/internal/music/variation', dependencies=[Depends(desktop_auth)], include_in_schema=False)
    async def music_variation(edit: MusicVariationRequest):
        from .music_lora import prepare_loras
        manager.require('music')
        original = manager.job(edit.job_id)
        files = (original['result'] or {}).get('files', [])
        if original['service'] != 'music' or original['status'] != 'succeeded' or edit.audio_index >= len(files):
            raise HTTPException(404, '原歌曲不存在或尚未完成')
        params = prepare_loras(manager.active.music.lora_dir, edit.music.model_dump())
        params['source_job_id'] = edit.job_id
        params['source_audio_index'] = edit.audio_index
        params['reference'] = edit.reference
        if edit.reference == 'audio':
            if not Path(manager.active.music.encoder_path).is_file():
                raise HTTPException(409, '请配置 SheetSage2 文件并重启音乐服务')
            path = Path(files[edit.audio_index]['path'])
            if not path.is_file():
                raise HTTPException(404, '原音频文件已不存在')
            params['reference_audio_path'] = str(path)
        else:
            score = next((s for s in (original['result'] or {}).get('scores', []) if s['audio_index'] == edit.audio_index), None)
            if not score:
                raise HTTPException(404, '原歌曲没有保存曲谱，请改用原音频参考')
            if edit.abc is not None:
                params['abc'] = edit.abc
            else:
                path = Path(score['path'])
                if not path.is_file() or path.stat().st_size > 1024 * 1024:
                    raise HTTPException(404, '原曲谱文件不存在或过大')
                params['abc'] = path.read_text('utf-8')
        return await response_for(await manager.submit('music', params), False)

    @app.post('/internal/music/separate', dependencies=[Depends(desktop_auth)], include_in_schema=False)
    async def separate_song(edit: MusicSeparateRequest):
        original = manager.job(edit.job_id)
        files = (original['result'] or {}).get('files', [])
        if original['service'] != 'music' or original['status'] != 'succeeded' or edit.audio_index >= len(files):
            raise HTTPException(404, '原歌曲不存在或尚未完成')
        if original['request'].get('operation') == 'separate':
            raise HTTPException(422, '请选择原曲进行人声分离')
        path = Path(files[edit.audio_index]['path'])
        if not path.is_file():
            raise HTTPException(404, '原音频文件已不存在')
        # Persist source linkage; titles/groups remain independent editable metadata.
        meta = original.get('song_metadata', {}).get(str(edit.audio_index), {})
        titles = original['request'].get('song_titles', [])
        title = meta.get('title') or files[edit.audio_index].get('title') or (titles[edit.audio_index] if edit.audio_index < len(titles) else original['request'].get('title')) or f'歌曲 {edit.job_id[:8]}_{edit.audio_index+1}'
        return await response_for(await manager.submit('music', {
            'operation': 'separate', 'source_job_id': edit.job_id, 'source_audio_index': edit.audio_index,
            'source_title': title, 'source_group': meta.get('group', ''), 'input_path': str(path),
            'count': 2, 'title': title, 'song_titles': [title + ' · 人声', title + ' · 伴奏']
        }), False)

    @app.exception_handler(Exception)
    async def internal_error(_, error):
        manager.log(f'API 错误: {error}')
        return JSONResponse(status_code=500, content={'detail': str(error)})

    @app.get('/health')
    def health():
        return {'status': 'ok', 'app': 'local-ai-service', 'version': '0.1.0'}

    @app.get('/v1/status', dependencies=secured)
    def status():
        return {'services': manager.status(), 'gpu_policy': '串行推理 · 每任务结束释放模型', 'current_job': manager.current, 'queued': manager.queue.qsize()}

    @app.get('/v1/config', dependencies=secured)
    def config():
        return manager.config

    @app.put('/v1/config', dependencies=secured)
    async def save_config(config: Config):
        async with manager.control_lock:
            manager.save(config)
        return {'saved': True, 'message': '配置已保存，需手动重启对应服务生效'}

    @app.post('/v1/services/{name}/restart', dependencies=secured)
    async def restart(name: str):
        return await manager.restart(name)

    @app.get('/v1/jobs', dependencies=secured)
    def jobs():
        return manager.jobs()

    @app.get('/v1/jobs/{job_id}', dependencies=secured)
    def job(job_id: str):
        return manager.job(job_id)

    @app.delete('/v1/jobs/{job_id}', dependencies=secured)
    async def cancel(job_id: str):
        return await manager.cancel(job_id)

    @app.get('/v1/jobs/{job_id}/files/{index}', dependencies=secured)
    def result_file(job_id: str, index: int):
        job = manager.job(job_id)
        files = (job['result'] or {}).get('files', [])
        if index < 0 or index >= len(files) or not Path(files[index]['path']).is_file():
            raise HTTPException(404, '结果文件不存在')
        return FileResponse(files[index]['path'], filename=Path(files[index]['path']).name)

    # Short-lived, file-scoped playback URLs support native audio Range requests.
    playback_tickets = {}
    playback_lock = threading.Lock()

    @app.post('/v1/playback', dependencies=secured)
    def create_playback(source: dict):
        url = source.get('source', '')
        if not isinstance(url, str):
            raise HTTPException(422, 'Invalid audio source')
        match = re.fullmatch(r'/v1/jobs/([^/]+)/files/(\d+)', url)
        if match:
            response = result_file(match[1], int(match[2]))
            path = Path(response.path)
        elif re.fullmatch(r'/v1/sounds/[^/]+/audio', url):
            path = manager.sound_path(url.split('/')[3])
        elif re.fullmatch(r'/v1/voices/[^/]+/audio', url):
            path = Path(voice_path(url.split('/')[3]))
        else:
            raise HTTPException(422, 'Invalid audio source')
        ticket = secrets.token_urlsafe(32)
        now = time.monotonic()
        with playback_lock:
            for key in list(playback_tickets):
                if playback_tickets[key][1] <= now:
                    del playback_tickets[key]
            if len(playback_tickets) >= 256:
                del playback_tickets[next(iter(playback_tickets))]
            playback_tickets[ticket] = (path, now + 21600)
        return {'url': '/v1/playback/' + ticket}

    @app.get('/v1/playback/{ticket}')
    def stream_playback(ticket: str):
        with playback_lock:
            entry = playback_tickets.get(ticket)
        if not entry or entry[1] <= time.monotonic() or not entry[0].is_file():
            raise HTTPException(404, 'Playback link expired or file missing')
        return FileResponse(entry[0], headers={'Cache-Control': 'private, no-store'})

    @app.get('/v1/jobs/{job_id}/scores/{index}', dependencies=secured)
    def result_score(job_id: str, index: int, download: bool = False):
        job = manager.job(job_id)
        scores = (job['result'] or {}).get('scores', [])
        if index < 0 or index >= len(scores):
            raise HTTPException(404, '曲谱不存在')
        path = Path(scores[index]['path'])
        if not path.is_file() or path.suffix != '.abc' or path.stat().st_size > 1024 * 1024:
            raise HTTPException(404, '曲谱文件不存在或无效')
        if download:
            return FileResponse(path, filename=path.name, media_type='text/plain; charset=utf-8')
        return {'abc': path.read_text('utf-8'), 'format': 'abc', 'audio_index': scores[index]['audio_index'], 'mode': scores[index]['mode']}

    async def response_for(job, wait):
        if not wait:
            return JSONResponse(status_code=202, content=job, headers={'Location': f'/v1/jobs/{job["id"]}'})
        while job['status'] in ('queued', 'running'):
            await asyncio.sleep(0.5)
            job = manager.job(job['id'])
        if job['status'] != 'succeeded':
            return JSONResponse(status_code=500, content=job)
        return {'id': job['id'], 'status': job['status'], **job['result']}

    @app.post('/v1/music/generate', dependencies=secured)
    async def music(request: MusicRequest, wait: bool = True):
        from .music_lora import prepare_loras
        manager.require('music')
        params = prepare_loras(manager.active.music.lora_dir, request.model_dump())
        return await response_for(await manager.submit('music', params), wait)

    @app.get('/v1/music/lora-options', dependencies=secured)
    def lora_options():
        from .music_lora import catalog
        return catalog(manager.active.music.lora_dir)

    from .models import SongMetadata, MusicWorkspaceRequest, MusicAnnotationRequest

    @app.put('/v1/music/jobs/{job_id}/songs/{index}/annotation', dependencies=secured)
    def annotate_music(job_id: str, index: int, annotation: MusicAnnotationRequest):
        return manager.annotate_music(job_id, index, annotation.rating, annotation.favorite)

    @app.get('/v1/music/workspaces', dependencies=secured)
    def music_workspaces():
        return manager.music_workspaces()

    @app.post('/v1/music/workspaces', dependencies=secured, status_code=201)
    def create_music_workspace(request: MusicWorkspaceRequest):
        return manager.create_music_workspace(request.name)

    @app.put('/v1/music/jobs/{job_id}/songs/{index}', dependencies=secured)
    def edit_song(job_id: str, index: int, metadata: SongMetadata):
        return manager.edit_song(job_id, index, metadata.title, metadata.group)

    @app.post('/v1/music/jobs/{job_id}/songs/{index}/played', dependencies=secured)
    def mark_music_played(job_id: str, index: int):
        return manager.mark_music_played(job_id, index)

    @app.post('/v1/sfx/generate', dependencies=secured)
    async def sfx(request: SfxRequest, wait: bool = True):
        """Generate 48 kHz mono sound effects with local MOSS-SoundEffect v2.0."""
        return await response_for(await manager.submit('sfx', request.model_dump()), wait)

    @app.post('/v1/uploads', dependencies=secured)
    async def upload(file: UploadFile = File(...)):
        extension = Path(file.filename or '').suffix.lower()
        if extension not in {'.wav', '.mp3', '.flac', '.ogg', '.m4a', '.aac', '.opus', '.mp4', '.mov', '.mkv', '.webm', '.avi'}:
            raise HTTPException(415, '不支持的音频或视频格式')
        upload_id = uuid.uuid4().hex + extension
        directory = manager.home / 'uploads'
        directory.mkdir(exist_ok=True)
        path = directory / upload_id
        size = 0
        try:
            with path.open('wb') as target:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > 512 * 1024 * 1024:
                        raise HTTPException(413, '单个上传文件不得超过 512 MB')
                    target.write(chunk)
            if size == 0:
                raise HTTPException(400, '上传文件为空')
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        finally:
            await file.close()
        return {'upload_id': upload_id, 'size': size}

    def upload_path(upload_id):
        path = manager.home / 'uploads' / upload_id
        if not upload_id or Path(upload_id).name != upload_id or '/' in upload_id or '\\' in upload_id or not inside(path, manager.home / 'uploads') or not path.is_file():
            raise HTTPException(404, '上传文件不存在')
        return str(path.resolve())

    preview_lock = asyncio.Semaphore(1)

    @app.post('/v1/uploads/{upload_id}/audio-preview', dependencies=secured)
    async def audio_preview(upload_id: str, service: Literal['music', 'tts', 'vc', 'auk', 'denoise', 'separation'] = 'music'):
        source = upload_path(upload_id)
        ffmpeg = getattr(manager.active, service).ffmpeg

        def extract():
            with tempfile.TemporaryDirectory(prefix='audio-preview-') as directory:
                target = Path(directory) / 'preview.wav'
                try:
                    subprocess.run([ffmpeg, '-nostdin', '-v', 'error', '-y', '-i', source,
                                    '-map', '0:a:0', '-vn', '-t', '900', '-ar', '24000', '-ac', '1',
                                    '-c:a', 'pcm_s16le', str(target)], check=True, capture_output=True,
                                   timeout=120, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                except FileNotFoundError:
                    raise HTTPException(409, '请配置 FFmpeg 并重启对应服务')
                except subprocess.TimeoutExpired:
                    raise HTTPException(422, '音轨提取超时，请尝试较短的视频')
                except subprocess.CalledProcessError:
                    raise HTTPException(422, '无法提取音轨，请确认文件包含可解码的音频')
                if not target.is_file() or target.stat().st_size <= 44:
                    raise HTTPException(422, '无法提取音轨，请确认文件包含可解码的音频')
                return {'audio_base64': base64.b64encode(target.read_bytes()).decode('ascii')}

        async with preview_lock:
            return await asyncio.to_thread(extract)

    @app.post('/internal/music/separate-upload', dependencies=[Depends(desktop_auth)], include_in_schema=False)
    async def separate_uploaded_music(request: MusicUploadSeparateRequest):
        path = upload_path(request.upload_id)
        title = request.title.strip() or '音频'
        return await response_for(await manager.submit('music', {
            'operation': 'separate', 'source_job_id': 'upload:' + request.upload_id, 'source_audio_index': 0,
            'source_title': title, 'source_group': '', 'input_path': path,
            'count': 2, 'title': title, 'song_titles': [title + ' · 人声', title + ' · 伴奏']
        }), False)

    @app.post('/internal/music/transcribe', dependencies=[Depends(desktop_auth)], include_in_schema=False)
    async def transcribe_reference(edit: MusicTranscribeRequest):
        manager.require('music')
        path = upload_path(edit.upload_id)
        if not Path(manager.active.music.encoder_path).is_file():
            raise HTTPException(409, '请配置 SheetSage2 文件并重启音乐服务')
        params = edit.model_dump(exclude={'upload_id'})
        params.update(workspace=edit.workspace.strip(), operation='transcribe', count=1,
                      generate_score=True, reference_audio_path=path, reference='audio')
        return await response_for(await manager.submit('music', params), False)

    @app.post('/internal/music/reference', dependencies=[Depends(desktop_auth)], include_in_schema=False)
    async def music_audio_reference(edit: MusicAudioReferenceRequest):
        from .music_lora import prepare_loras
        manager.require('music')
        path = upload_path(edit.upload_id)
        if not Path(manager.active.music.encoder_path).is_file():
            raise HTTPException(409, '请配置 SheetSage2 文件并重启音乐服务')
        params = prepare_loras(manager.active.music.lora_dir, edit.music.model_dump())
        params.update(reference_audio_path=path, reference='audio')
        return await response_for(await manager.submit('music', params), False)

    @app.post('/v1/audio/edit', dependencies=secured)
    async def audio_edit(request: AukRequest, wait: bool = True):
        params = request.model_dump()
        if request.upload_id:
            params['input_path'] = upload_path(request.upload_id)
        return await response_for(await manager.submit('auk', params), wait)

    def voice_path(voice_id):
        if voice_id not in VOICE_IDS:
            raise HTTPException(404, '音色不存在')
        root = Path(manager.active.vc.voices_dir)
        path = root / (voice_id + '.wav')
        if not manager.active.vc.voices_dir or not inside(path, root) or not path.is_file():
            raise HTTPException(503, '该预设音色参考尚未准备，请生成参考或上传自己的音频')
        return path.resolve()

    @app.get('/v1/voices', dependencies=secured)
    def voices():
        result = []
        for voice in VOICES:
            try:
                voice_path(voice['id'])
                available = True
            except HTTPException:
                available = False
            result.append({**voice, 'vc_available':available, 'preview_url':f'/v1/voices/{voice["id"]}/audio' if available else None})
        return result

    @app.get('/v1/voices/{voice_id}/audio', dependencies=secured)
    def preview_voice(voice_id: str):
        return FileResponse(voice_path(voice_id), filename=voice_id + '.wav')

    @app.get('/v1/tts/models', dependencies=secured)
    def tts_models():
        issues = check_breeze(manager.active.tts.model_dump())
        return {'models': [
            {'id': 'qwen3-tts', 'status': manager.states.get('tts', {}).get('status', 'checking'), 'modes': ['preset', 'clone'], 'speakers': list(VOICE_IDS)},
            {'id': 'breeze-tts2', 'status': 'stopped' if not manager.active.tts.enabled else 'needs_config' if issues else 'ready', 'modes': ['design', 'clone', 'direction'], 'languages': ['Auto', 'Chinese', 'English'], 'speakers': [], 'message': '；'.join(issues)}],
            'download': breeze_download.snapshot()}

    @app.post('/internal/tts/breeze/download', dependencies=[Depends(desktop_auth)], include_in_schema=False)
    async def download_breeze():
        async def complete(path):
            async with manager.control_lock:
                updated = manager.config.model_copy(deep=True)
                updated.tts.breeze_model_dir = path
                manager.save(updated)
        return breeze_download.start(complete)

    @app.delete('/internal/tts/breeze/download', dependencies=[Depends(desktop_auth)], include_in_schema=False)
    def cancel_breeze_download():
        breeze_download.cancelled.set()
        return breeze_download.snapshot()

    @app.post('/v1/tts/generate', dependencies=secured)
    async def tts(request: TtsRequest, wait: bool = True):
        if request.model == 'qwen3-tts':
            manager.require('tts')
        params = request.model_dump()
        if request.reference_upload_id:
            params['reference_path'] = upload_path(request.reference_upload_id)
        return await response_for(await manager.submit('tts', params), wait)

    @app.post('/v1/voice/convert', dependencies=secured)
    async def voice_convert(request: VcRequest, wait: bool = True):
        manager.require('vc')
        params = request.model_dump()
        params['input_path'] = upload_path(request.source_upload_id)
        params['reference_path'] = upload_path(request.reference_upload_id) if request.reference_upload_id else str(voice_path(request.target_voice))
        return await response_for(await manager.submit('vc', params), wait)

    @app.post('/v1/denoise', dependencies=secured)
    async def denoise(request: DenoiseRequest, wait: bool = True):
        return await submit_audio('denoise', request, wait)

    async def submit_audio(service, request, wait):
        upload_id = request.upload_id
        if Path(upload_id).name != upload_id or '/' in upload_id or '\\' in upload_id or not (manager.home / 'uploads' / upload_id).is_file():
            raise HTTPException(404, '上传文件不存在')
        params = request.model_dump(exclude_none=True)
        params['input_path'] = str(manager.home / 'uploads' / upload_id)
        return await response_for(await manager.submit(service, params), wait)

    @app.post('/v1/denoise/file', dependencies=secured)
    async def denoise_file(file: UploadFile = File(...), segment_seconds: float | None = Form(None, ge=4, le=120), max_duration: int | None = Form(None, ge=1, le=7200), wait: bool = True):
        manager.require('denoise')
        uploaded = await upload(file)
        return await denoise(DenoiseRequest(upload_id=uploaded['upload_id'], segment_seconds=segment_seconds, max_duration=max_duration), wait)

    @app.post('/v1/separate', dependencies=secured)
    async def separate(request: SeparationRequest, wait: bool = True):
        """Separate speakers, vocals/accompaniment, or queue both modes."""
        path = upload_path(request.upload_id)
        services = ['separation', 'music'] if request.mode == 'both' else ['music' if request.mode == 'music' else 'separation']
        for service in services:
            manager.require(service)
        if manager.queue.maxsize - manager.queue.qsize() < len(services):
            raise HTTPException(429, '任务队列已满（32），请稍后重试')
        jobs = []
        for service in services:
            if service == 'music':
                title = request.title.strip() or '音频'
                params = {'operation': 'separate', 'source_job_id': 'upload:' + request.upload_id,
                          'source_audio_index': 0, 'source_title': title, 'source_group': '',
                          'input_path': path, 'count': 2, 'title': title,
                          'song_titles': [title + ' · 人声', title + ' · 伴奏']}
            else:
                params = request.model_dump(exclude_none=True, exclude={'mode', 'title'})
                params['input_path'] = path
            try:
                jobs.append(await manager.submit(service, params))
            except HTTPException as error:
                if not jobs:
                    raise
                return JSONResponse(status_code=error.status_code, content={'detail': error.detail, 'status': 'partial', 'jobs': jobs})
        if request.mode != 'both':
            return await response_for(jobs[0], wait)
        if not wait:
            return JSONResponse(status_code=202, content={'mode': 'both', 'jobs': jobs})
        results = await asyncio.gather(*(response_for(job, True) for job in jobs))
        finished = [manager.job(job['id']) for job in jobs]
        failed = any(isinstance(result, JSONResponse) for result in results)
        return JSONResponse(status_code=500 if failed else 200, content={
            'mode': 'both', 'status': 'failed' if failed else 'succeeded', 'jobs': finished,
            'files': [file for job in finished for file in (job['result'] or {}).get('files', [])]})

    @app.post('/v1/separate/file', dependencies=secured)
    async def separate_file(file: UploadFile = File(...), mode: Literal['speakers', 'music', 'both'] = Form('speakers'), title: str = Form('', max_length=120), segment_seconds: float | None = Form(None, ge=2, le=120), max_duration: int | None = Form(None, ge=1, le=7200), wait: bool = True):
        uploaded = await upload(file)
        return await separate(SeparationRequest(upload_id=uploaded['upload_id'], mode=mode, title=title, segment_seconds=segment_seconds, max_duration=max_duration), wait)

    @app.get('/v1/sounds', dependencies=secured)
    def sounds(category: str = '', q: str = '', limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
        return manager.sounds(category, q, limit, offset)

    @app.get('/v1/categories', dependencies=secured)
    def categories():
        manager.require('library')
        root = str(Path(manager.active.library.directory).resolve())
        with connect(manager.active.library.database) as db:
            return [dict(row) for row in db.execute('SELECT category, count(*) AS count FROM sounds WHERE root=? GROUP BY category ORDER BY category', (root,))]

    @app.post('/v1/sounds/scan', dependencies=secured)
    async def scan():
        manager.require('library')
        if manager.scan_lock.locked():
            raise HTTPException(409, '正在扫描中')
        async with manager.scan_lock:
            return await asyncio.to_thread(manager.scan_sync)

    @app.get('/v1/sounds/{sound_id}/audio', dependencies=secured)
    def sound_file(sound_id: str):
        path = manager.sound_path(sound_id)
        return FileResponse(path, filename=path.name)

    @app.get('/v1/logs', dependencies=secured)
    def logs():
        path = manager.home / 'service.log'
        if not path.exists():
            return []
        with path.open('rb') as f:
            f.seek(max(0, path.stat().st_size - 64000))
            return f.read().decode('utf-8', errors='replace').splitlines()[-200:]

    return app
