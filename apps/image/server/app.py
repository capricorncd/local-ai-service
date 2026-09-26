import asyncio
import io
import json
import os
import secrets
import sqlite3
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, UploadFile, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from PIL import Image, ImageOps
from domain import Config, Generate, Project, inspect_models, build_prompt
from recents import RecentStore

Image.MAX_IMAGE_PIXELS = 20_000_000

def create_app(home: Path):
    home.mkdir(parents=True, exist_ok=True)
    uploads, outputs = home / 'uploads', home / 'outputs'
    uploads.mkdir(exist_ok=True)
    outputs.mkdir(exist_ok=True)
    token_path = home / 'api-token'
    if not token_path.exists():
        token_path.write_text(secrets.token_urlsafe(32))
    token = token_path.read_text().strip()
    config_path = home / 'config.json'
    lock = threading.RLock()
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='image-jobs')
    processes = {}
    stopping = threading.Event()
    db_path = home / 'images.sqlite3'
    recents = RecentStore(db_path)

    def sql(query, params=(), fetch=False):
        with sqlite3.connect(db_path) as db:
            db.row_factory = sqlite3.Row
            cur = db.execute(query, params)
            return [dict(row) for row in cur.fetchall()] if fetch else None

    sql('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, created REAL, status TEXT, request TEXT, error TEXT, progress INTEGER DEFAULT 0)')
    sql('CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, name TEXT, updated REAL)')
    projects_dir = home / 'projects'
    projects_dir.mkdir(exist_ok=True)
    sql("UPDATE jobs SET status='failed',error='Application stopped before completion' WHERE status IN ('queued','running')")

    def config():
        return Config.model_validate_json(config_path.read_text('utf-8')) if config_path.exists() else Config()

    def uploaded(id):
        if len(id) != 32 or any(c not in '0123456789abcdef' for c in id):
            raise HTTPException(404, 'Image not found')
        path = uploads / f'{id}.png'
        if not path.is_file():
            raise HTTPException(404, 'Image not found')
        return path

    def row(id):
        rows = sql('SELECT * FROM jobs WHERE id=?', (id,), True)
        if not rows:
            raise HTTPException(404, 'Job not found')
        result = rows[0]
        result['request'] = json.loads(result['request'])
        result['file'] = str(outputs / id / 'image.png') if result['status'] == 'completed' else None
        return result

    def run(id, req, cfg):
        with lock:
            if stopping.is_set() or row(id)['status'] != 'queued':
                return
            sql("UPDATE jobs SET status='running' WHERE id=?", (id,))
        directory = outputs / id
        directory.mkdir(exist_ok=True)
        payload = {'request': req.model_dump(), 'config': cfg.model_dump(), 'prompt': build_prompt(req),
                   'references': [str(uploaded(i)) for i in req.references],
                   'mask': str(uploaded(req.mask)) if req.mask else None, 'output': str(directory / 'image.png')}
        (directory / 'input.json').write_text(json.dumps(payload, ensure_ascii=False), 'utf-8')
        try:
            with (directory / 'worker.log').open('w', encoding='utf-8') as log:
                with lock:
                    if row(id)['status'] == 'cancelled' or stopping.is_set():
                        return
                    proc = subprocess.Popen([cfg.python, str(Path(__file__).with_name('worker.py')), str(directory / 'input.json')],
                        stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                        env={**os.environ, 'PYTHONUTF8':'1', 'PYTHONUNBUFFERED':'1'},
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                    processes[id] = proc
                while proc.poll() is None:
                    try:
                        progress = json.loads((directory / 'progress.json').read_text())['progress']
                        sql('UPDATE jobs SET progress=? WHERE id=?', (progress, id))
                    except (OSError, ValueError, KeyError):
                        pass
                    time.sleep(.5)
                if proc.returncode != 0:
                    raise RuntimeError((directory / 'worker.log').read_text('utf-8')[-4000:])
                if not (directory / 'image.png').is_file():
                    raise RuntimeError('Inference exited without an image')
            with lock:
                if row(id)['status'] != 'cancelled':
                    sql("UPDATE jobs SET status='completed',progress=100 WHERE id=?", (id,))
        except Exception as e:
            with lock:
                if row(id)['status'] != 'cancelled':
                    sql("UPDATE jobs SET status='failed',error=? WHERE id=?", (str(e), id))
        finally:
            with lock:
                processes.pop(id, None)

    @asynccontextmanager
    async def lifespan(app):
        yield
        stopping.set()
        with lock:
            for proc in processes.values():
                proc.terminate()
        pool.shutdown(wait=True, cancel_futures=True)

    app = FastAPI(title='Local AI Image', lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=['http://127.0.0.1:1421', 'http://localhost:1421', 'http://tauri.localhost', 'tauri://localhost'], allow_methods=['GET','POST','PUT'], allow_headers=['Authorization','Content-Type'])

    def auth(authorization: str = Header(default='')):
        if not secrets.compare_digest(authorization, f'Bearer {token}'):
            raise HTTPException(401, 'Unauthorized')

    @app.middleware('http')
    async def body_limit(request, call_next):
        # Bound streamed bodies too; a forged Content-Length must not bypass limits.
        if request.method in ('POST','PUT'):
            from starlette.responses import JSONResponse
            total = 0
            body = bytearray()
            async for chunk in request.stream():
                total += len(chunk)
                if total > 200 * 1024 * 1024:
                    return JSONResponse({'detail':'Request exceeds 200 MB'}, status_code=413)
                body.extend(chunk)
            request._body = bytes(body)
        return await call_next(request)

    @app.get('/health')
    def health():
        return {'status': 'ready', 'app':'local-ai-image', 'version':'0.1.0'}

    @app.get('/v1/recents', dependencies=[Depends(auth)])
    def recent_list():
        return recents.list()

    @app.post('/v1/recents', dependencies=[Depends(auth)])
    def recent_save(project: Project):
        return recents.save(project)

    @app.get('/v1/recents/{id}', dependencies=[Depends(auth)])
    def recent_open(id: str):
        value = recents.get(id)
        if value is None:
            raise HTTPException(404, 'Operation record not found')
        return value

    @app.get('/v1/config', dependencies=[Depends(auth)])
    def get_config():
        cfg = config()
        return {'config': cfg.model_dump(), 'models': inspect_models(cfg),
                'runtime_checks': {'python':Path(cfg.python).is_file(), 'core':(Path(cfg.core) / 'comfy/text_encoders/qwen_image21.py').is_file()},
                'runtime_ready': Path(cfg.python).is_file() and (Path(cfg.core) / 'comfy/text_encoders/qwen_image21.py').is_file()}

    @app.put('/v1/config', dependencies=[Depends(auth)])
    def save_config(cfg: Config):
        temp = config_path.with_suffix('.tmp')
        with lock:
            temp.write_text(cfg.model_dump_json(indent=2), 'utf-8')
            temp.replace(config_path)
        return get_config()

    @app.post('/v1/images', dependencies=[Depends(auth)])
    async def upload(file: UploadFile):
        data = await file.read(32 * 1024 * 1024 + 1)
        await file.close()
        if len(data) > 32 * 1024 * 1024:
            raise HTTPException(413, 'Image exceeds 32 MB')
        try:
            with Image.open(io.BytesIO(data)) as source:
                if source.width * source.height > 20_000_000:
                    raise ValueError('Image exceeds 20 megapixels')
                image = ImageOps.exif_transpose(source).convert('RGBA')
                id = uuid.uuid4().hex
                image.save(uploads / f'{id}.png')
            return {'id': id, 'width': image.width, 'height': image.height, 'name': file.filename}
        except (OSError, ValueError, Image.DecompressionBombError) as e:
            raise HTTPException(400, str(e)) from e

    @app.get('/v1/images/{id}', dependencies=[Depends(auth)])
    def get_image(id: str):
        return FileResponse(uploaded(id), media_type='image/png')

    @app.post('/v1/jobs', status_code=202, dependencies=[Depends(auth)])
    def generate(req: Generate):
        cfg = config()
        missing = [m['role'] for m in inspect_models(cfg) if not m['ready']]
        if missing:
            raise HTTPException(409, f'Model files missing or incomplete: {", ".join(missing)}')
        if not Path(cfg.python).is_file() or not (Path(cfg.core) / 'comfy/text_encoders/qwen_image21.py').is_file():
            raise HTTPException(409, 'Install the image runtime first: apps/image/scripts/setup.ps1')
        for ref in req.references:
            uploaded(ref)
        if req.mask:
            with Image.open(uploaded(req.mask)) as mask, Image.open(uploaded(req.references[0])) as source:
                if mask.size != source.size:
                    raise HTTPException(422, 'Mask dimensions must match the first reference image')
                if mask.convert('L').getextrema()[1] == 0:
                    raise HTTPException(422, 'Mask is empty')
        if req.seed == -1:
            req = req.model_copy(update={'seed': secrets.randbelow(2**32)})
        id = uuid.uuid4().hex
        sql('INSERT INTO jobs(id,created,status,request) VALUES(?,?,?,?)', (id,time.time(),'queued',req.model_dump_json()))
        pool.submit(run, id, req, cfg)
        return row(id)

    @app.get('/v1/jobs', dependencies=[Depends(auth)])
    def jobs():
        return [row(r['id']) for r in sql('SELECT id FROM jobs ORDER BY created DESC LIMIT 100', fetch=True)]

    @app.get('/v1/jobs/{id}', dependencies=[Depends(auth)])
    def get_job(id: str):
        return row(id)

    @app.post('/v1/jobs/{id}/cancel', dependencies=[Depends(auth)])
    def cancel(id: str):
        with lock:
            if row(id)['status'] in ('queued', 'running'):
                sql("UPDATE jobs SET status='cancelled' WHERE id=?", (id,))
                proc = processes.get(id)
                if proc and proc.poll() is None:
                    proc.terminate()
        return row(id)

    @app.get('/v1/jobs/{id}/image', dependencies=[Depends(auth)])
    def result(id: str):
        job = row(id)
        if not job['file'] or not Path(job['file']).is_file():
            raise HTTPException(404, 'Image unavailable')
        return FileResponse(job['file'], media_type='image/png', filename=f'{id}.png')

    @app.post('/v1/jobs/{id}/reference', dependencies=[Depends(auth)])
    def reuse(id: str):
        job = row(id)
        if not job['file']:
            raise HTTPException(409, 'Image is not ready')
        import shutil
        new_id = uuid.uuid4().hex
        shutil.copyfile(job['file'], uploads / f'{new_id}.png')
        with Image.open(job['file']) as im:
            return {'id':new_id,'width':im.width,'height':im.height,'name':f'{id}.png'}

    def project_path(id):
        if len(id) != 32 or any(c not in '0123456789abcdef' for c in id):
            raise HTTPException(404, 'Project not found')
        return projects_dir / f'{id}.laimage'

    def store_project(id, project):
        import base64
        # Decode for validation only; retain exact original bytes in project data.
        for source in [l.source for l in project.layers] + ([project.mask] if project.mask else []):
            try:
                raw = base64.b64decode(source.split(',',1)[1], validate=True)
                with Image.open(io.BytesIO(raw)) as im:
                    if im.width*im.height > 20_000_000:
                        raise ValueError('Image pixel limit exceeded')
                    im.verify()
            except (ValueError,OSError,Image.DecompressionBombError) as e:
                raise HTTPException(422, 'Invalid embedded image') from e
        path = project_path(id)
        with lock:
            temp = path.with_suffix('.tmp')
            temp.write_text(project.model_dump_json(), 'utf-8')
            temp.replace(path)
            sql('INSERT OR REPLACE INTO projects(id,name,updated) VALUES(?,?,?)', (id,project.name,time.time()))
        return {'id':id,'name':project.name}

    @app.post('/v1/projects', status_code=201, dependencies=[Depends(auth)])
    def create_project(project: Project):
        return store_project(uuid.uuid4().hex, project)

    @app.put('/v1/projects/{id}', dependencies=[Depends(auth)])
    def update_project(id: str, project: Project):
        if not project_path(id).is_file():
            raise HTTPException(404, 'Project not found')
        return store_project(id, project)

    @app.get('/v1/projects', dependencies=[Depends(auth)])
    def projects():
        return sql('SELECT * FROM projects ORDER BY updated DESC', fetch=True)

    @app.get('/v1/projects/{id}', dependencies=[Depends(auth)])
    def get_project(id: str):
        path = project_path(id)
        if not path.is_file():
            raise HTTPException(404, 'Project not found')
        return FileResponse(path, media_type='application/json', filename=f'{id}.laimage')

    @app.post('/v1/projects/{id}/generate', status_code=202, dependencies=[Depends(auth)])
    def generate_project(id: str):
        import base64
        path = project_path(id)
        if not path.is_file():
            raise HTTPException(404, 'Project not found')
        project = Project.model_validate_json(path.read_text('utf-8'))
        layers = [l for l in project.layers if l.visible and l.reference]
        if len(layers) > 10:
            raise HTTPException(422, 'Select no more than 10 reference layers')
        def decode(data):
            with Image.open(io.BytesIO(base64.b64decode(data.split(',',1)[1]))) as im:
                return im.convert('RGBA')
        def persist(image):
            image_id = uuid.uuid4().hex
            image.save(uploads / f'{image_id}.png')
            return image_id
        references = []
        for layer in layers:
            canvas = Image.new('RGBA', (project.width,project.height))
            image = decode(layer.source)
            size = (max(1,round(layer.width*layer.scale)),max(1,round(layer.height*layer.scale)))
            # Crop through a bounded affine transform rather than allocating huge scaled layers.
            image = image.transform(canvas.size, Image.Transform.AFFINE,
                (image.width/size[0],0,-layer.x*image.width/size[0],0,image.height/size[1],-layer.y*image.height/size[1]),
                resample=Image.Resampling.BICUBIC)
            image.putalpha(image.getchannel('A').point(lambda value:round(value*layer.opacity)))
            canvas.alpha_composite(image)
            references.append(persist(canvas))
        mask_id = None
        if project.mode in ('brush','circle','mask') and project.mask:
            mask = decode(project.mask)
            if mask.size != (project.width,project.height):
                raise HTTPException(422,'Mask dimensions must match the canvas')
            black = Image.new('RGBA',mask.size,(0,0,0,255))
            black.alpha_composite(mask)
            mask_id = persist(black)
        try:
            req = Generate(**{key:getattr(project,key) for key in ('mode','prompt','negative','width','height','steps','cfg','seed')},references=references,mask=mask_id)
        except ValueError as e:
            raise HTTPException(422,str(e)) from e
        return generate(req)
    return app
