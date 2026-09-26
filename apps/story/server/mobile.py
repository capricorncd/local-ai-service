"""Opt-in LAN gateway. Desktop credentials and service configuration stay on loopback."""
import hashlib
import io
import ipaddress
import json
import logging
import secrets
import socket
import threading
import time
from contextlib import asynccontextmanager, closing
from pathlib import Path

import qrcode
import qrcode.image.svg
import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from domain import Project, uid
from storage import atomic_json


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def lan_addresses():
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)}
        return sorted(address for address in addresses if ipaddress.ip_address(address).is_private and not ipaddress.ip_address(address).is_loopback)
    except OSError:
        return []


class MobileConfig(BaseModel):
    enabled: bool
    port: int = Field(default=19879, ge=1024, le=65535)


class PairCode(BaseModel):
    address: str


class Claim(BaseModel):
    code: str = Field(min_length=20, max_length=100)
    name: str = Field(min_length=1, max_length=80)


class Poll(BaseModel):
    secret: str = Field(min_length=20, max_length=100)


class Decision(BaseModel):
    approve: bool


class MobileGateway:
    def __init__(self, store, dist=None):
        self.store = store
        self.dist = Path(dist) if dist else Path(__file__).resolve().parents[1] / 'dist'
        self.config_path = store.home / 'mobile.json'
        self.config = MobileConfig(enabled=False)
        if self.config_path.exists():
            self.config = MobileConfig.model_validate_json(self.config_path.read_text('utf-8'))
        self.enabled = False
        self.error = ''
        self.server = None
        self.thread = None
        self.lock = threading.RLock()
        self.control_lock = threading.Lock()
        self.codes = {}
        self.pending = {}
        with closing(store.connect()) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS mobile_devices (id TEXT PRIMARY KEY, name TEXT NOT NULL, token_hash TEXT UNIQUE NOT NULL, created REAL NOT NULL, expires REAL NOT NULL)')
        self.app = self.create_gateway()

    def prune(self):
        now = time.time()
        self.codes = {key: value for key, value in self.codes.items() if value > now}
        self.pending = {key: value for key, value in self.pending.items() if value['expires'] > now}

    def status(self):
        with self.lock, closing(self.store.connect()) as db:
            self.prune()
            devices = [dict(zip(('id', 'name', 'created', 'expires'), row)) for row in db.execute('SELECT id,name,created,expires FROM mobile_devices WHERE expires>? ORDER BY created DESC', (time.time(),))]
            pending = [{key: item[key] for key in ('id', 'name', 'expires')} for item in self.pending.values() if item['status'] == 'pending']
            return {'enabled': self.enabled, 'port': self.config.port, 'addresses': lan_addresses(), 'devices': devices, 'pending': pending, 'error': self.error}

    def start(self):
        if self.enabled:
            return
        if not (self.dist / 'mobile.html').is_file():
            raise HTTPException(409, '移动端页面尚未构建，请先构建剧本应用')
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            listener.bind(('0.0.0.0', self.config.port))
            listener.listen(128)
        except OSError as exc:
            listener.close()
            raise HTTPException(409, f'局域网端口 {self.config.port} 无法使用：{exc}')
        self.server = uvicorn.Server(uvicorn.Config(self.app, access_log=False, proxy_headers=False, log_config=None))
        self.thread = threading.Thread(target=self.server.run, kwargs={'sockets': [listener]}, daemon=True, name='story-mobile')
        self.enabled = True
        self.thread.start()
        for _ in range(100):
            if self.server.started:
                self.error = ''
                return
            if not self.thread.is_alive():
                break
            time.sleep(.02)
        self.stop()
        listener.close()
        raise HTTPException(503, '移动端服务启动失败，请检查 launcher.log')

    def stop(self):
        self.enabled = False
        with self.lock:
            self.codes.clear()
            self.pending.clear()
        if self.server:
            self.server.should_exit = True
        if self.thread:
            self.thread.join(timeout=4)
        self.server = None
        self.thread = None

    def configure(self, value):
        with self.control_lock:
            if self.enabled and (not value.enabled or value.port != self.config.port):
                self.stop()
            self.config = value
            if value.enabled:
                self.start()
            else:
                self.stop()
            atomic_json(self.config_path, self.config.model_dump())
            return self.status()

    def new_code(self, address):
        with self.lock:
            if not self.enabled:
                raise HTTPException(409, '请先开启局域网访问')
            if address not in lan_addresses():
                raise HTTPException(422, '请选择电脑当前的局域网地址')
            self.prune()
            self.codes.clear()
            code = secrets.token_urlsafe(32)
            expires = time.time() + 300
            self.codes[digest(code)] = expires
            url = f'http://{address}:{self.config.port}/mobile#pair={code}'
            qr = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, border=4)
            output = io.BytesIO()
            qr.save(output)
            return {'url': url, 'expires': expires, 'svg': output.getvalue().decode()}

    def claim(self, req):
        with self.lock:
            self.prune()
            if self.codes.pop(digest(req.code), 0) <= time.time():
                raise HTTPException(410, '二维码已失效，请在电脑端刷新后重新扫描')
            if len(self.pending) >= 50:
                raise HTTPException(429, '待绑定设备过多，请稍后重试')
            secret = secrets.token_urlsafe(32)
            item = {'id': uid(), 'name': req.name.strip() or '手机', 'expires': time.time() + 300, 'status': 'pending', 'secret_hash': digest(secret)}
            self.pending[item['id']] = item
            return {'id': item['id'], 'secret': secret}

    def decide(self, id, approve):
        with self.lock:
            self.prune()
            item = self.pending.get(id)
            if not item or item['status'] != 'pending':
                raise HTTPException(404, '绑定请求已过期或已处理')
            if approve:
                token = secrets.token_urlsafe(32)
                with closing(self.store.connect()) as db, db:
                    db.execute('INSERT INTO mobile_devices VALUES (?,?,?,?,?)', (id, item['name'], digest(token), time.time(), time.time() + 90 * 86400))
                item.update(status='approved', token=token)
            else:
                item['status'] = 'rejected'
            return {'ok': True}

    def revoke(self, id):
        with self.lock, closing(self.store.connect()) as db, db:
            db.execute('DELETE FROM mobile_devices WHERE id=?', (id,))
            self.pending.pop(id, None)
            return {'ok': True}

    def authenticate(self, authorization: str = Header(default='')):
        if not self.enabled:
            raise HTTPException(503, '电脑已关闭局域网访问')
        token = authorization.removeprefix('Bearer ')
        with closing(self.store.connect()) as db:
            row = db.execute('SELECT id,name FROM mobile_devices WHERE token_hash=? AND expires>?', (digest(token), time.time())).fetchone()
        if not row:
            raise HTTPException(401, '绑定已失效，请重新扫码绑定')
        return {'id': row[0], 'name': row[1]}

    def create_gateway(self):
        app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

        @app.middleware('http')
        async def boundary(request, call_next):
            if not self.enabled:
                return JSONResponse({'detail': '局域网访问已关闭'}, status_code=503)
            peer = request.client.host if request.client else ''
            try:
                address = ipaddress.ip_address(peer)
                if not (address.is_private or address.is_loopback):
                    return JSONResponse({'detail': '仅允许局域网访问'}, status_code=403)
            except ValueError:
                return JSONResponse({'detail': '无效的访问地址'}, status_code=403)
            if request.method in ('POST', 'PUT'):
                body = bytearray()
                async for chunk in request.stream():
                    body.extend(chunk)
                    if len(body) > 20 * 1024 * 1024:
                        return JSONResponse({'detail': '内容超过 20 MB'}, status_code=413)
                request._body = bytes(body)
            response = await call_next(request)
            response.headers['Cache-Control'] = 'no-store'
            response.headers['Referrer-Policy'] = 'no-referrer'
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'DENY'
            return response

        @app.get('/')
        @app.get('/mobile')
        def page():
            if not (self.dist / 'mobile.html').is_file():
                raise HTTPException(503, '移动页面尚未构建')
            return FileResponse(self.dist / 'mobile.html')

        @app.post('/pair/claim')
        def claim(req: Claim):
            return self.claim(req)

        @app.post('/pair/{id}/poll')
        def poll(id: str, req: Poll):
            with self.lock:
                self.prune()
                item = self.pending.get(id)
                if not item or not secrets.compare_digest(item['secret_hash'], digest(req.secret)):
                    raise HTTPException(410, '绑定请求已过期，请重新扫码')
                return {'status': item['status'], **({'token': item['token']} if item['status'] == 'approved' else {})}

        @app.get('/v1/session')
        def session(device=Depends(self.authenticate)):
            return device

        @app.get('/v1/projects')
        def projects(device=Depends(self.authenticate)):
            result = []
            for id in self.store.roots:
                p = self.store.load(id)
                result.append({'id': id, 'name': p.name, 'updated': p.updated, 'episodes': sum(len(c.episodes) for c in p.chapters)})
            return sorted(result, key=lambda p: p['updated'], reverse=True)

        @app.get('/v1/projects/{id}')
        def project(id: str, device=Depends(self.authenticate)):
            return self.store.load(id)

        @app.put('/v1/projects/{id}')
        def save(id: str, project: Project, device=Depends(self.authenticate)):
            return self.store.save(id, project, '手机编辑 · ' + device['name'])

        @app.get('/v1/projects/{id}/media/{name}')
        def media(id: str, name: str, device=Depends(self.authenticate)):
            return FileResponse(self.store.media(id, 'media/' + name))

        @app.get('/v1/projects/{id}/history')
        def history(id: str, device=Depends(self.authenticate)):
            return self.store.versions(id)

        @app.get('/v1/projects/{id}/history/{revision}')
        def version(id: str, revision: str, device=Depends(self.authenticate)):
            return self.store.history(id, revision)

        app.mount('/assets', StaticFiles(directory=self.dist / 'assets', check_dir=False), name='assets')
        return app


def register_mobile(app, store, secured):
    gateway = MobileGateway(store)
    app.state.mobile = gateway

    @asynccontextmanager
    async def lifespan(app):
        if gateway.config.enabled:
            try:
                gateway.start()
            except Exception as exc:
                gateway.error = str(exc)
                logging.getLogger('uvicorn.error').exception('Mobile gateway startup failed')
        try:
            yield
        finally:
            gateway.stop()
    app.router.lifespan_context = lifespan

    @app.get('/v1/mobile', dependencies=secured)
    def status():
        return gateway.status()

    @app.put('/v1/mobile', dependencies=secured)
    def configure(req: MobileConfig):
        return gateway.configure(req)

    @app.post('/v1/mobile/pair', dependencies=secured)
    def pair(req: PairCode):
        return gateway.new_code(req.address)

    @app.post('/v1/mobile/pending/{id}', dependencies=secured)
    def approve(id: str, req: Decision):
        return gateway.decide(id, req.approve)

    @app.post('/v1/mobile/devices/{id}/revoke', dependencies=secured)
    def revoke(id: str):
        return gateway.revoke(id)
