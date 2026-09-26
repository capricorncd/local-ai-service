import hashlib
import socket
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
from app import create_app
from mobile import MobileGateway, MobileConfig


@pytest.fixture
def mobile(tmp_path, monkeypatch):
    monkeypatch.setattr('mobile.lan_addresses', lambda: ['192.168.1.10'])
    app = create_app(tmp_path / 'home')
    with TestClient(app) as desktop:
        desktop.headers['Authorization'] = 'Bearer ' + (tmp_path / 'home' / 'api-token').read_text()
        project = desktop.post('/v1/projects/open', json={'name': '手机测试'}).json()
        gateway = app.state.mobile
        gateway.dist = tmp_path / 'web'
        gateway.dist.mkdir()
        (gateway.dist / 'mobile.html').write_text('<html>Mobile preview</html>')
        gateway.enabled = True
        with TestClient(gateway.app, client=('192.168.1.20', 5050)) as phone:
            yield desktop, phone, gateway, project


def bind(desktop, phone, name='测试手机'):
    qr = desktop.post('/v1/mobile/pair', json={'address': '192.168.1.10'})
    assert qr.status_code == 200, qr.text
    assert '<svg' in qr.json()['svg']
    code = parse_qs(urlsplit(qr.json()['url']).fragment)['pair'][0]
    claim = phone.post('/pair/claim', json={'code': code, 'name': name})
    assert claim.status_code == 200, claim.text
    credentials = claim.json()
    assert phone.post('/pair/claim', json={'code': code, 'name': name}).status_code == 410
    assert phone.post('/pair/' + credentials['id'] + '/poll', json={'secret': credentials['secret']}).json() == {'status': 'pending'}
    assert desktop.post('/v1/mobile/pending/' + credentials['id'], json={'approve': True}).status_code == 200
    result = phone.post('/pair/' + credentials['id'] + '/poll', json={'secret': credentials['secret']}).json()
    assert result['status'] == 'approved'
    phone.headers['Authorization'] = 'Bearer ' + result['token']
    return credentials, result['token']


def test_binding_edit_history_conflict_and_revoke(mobile):
    desktop, phone, gateway, project = mobile
    assert phone.get('/v1/projects').status_code == 401
    credentials, token = bind(desktop, phone)
    assert phone.get('/v1/session').json()['name'] == '测试手机'
    assert 'directory' not in phone.get('/v1/projects').json()[0]
    url = '/v1/projects/' + project['id']
    draft = phone.get(url).json()
    draft['chapters'][0]['episodes'][0]['script'] = '手机新增的剧本'
    result = phone.put(url, json=draft)
    assert result.status_code == 200, result.text
    assert desktop.get(url).json()['chapters'][0]['episodes'][0]['script'] == '手机新增的剧本'
    history = phone.get(url + '/history').json()
    assert history[0]['reason'] == '手机编辑 · 测试手机'
    assert phone.get(url + '/history/' + history[0]['id']).status_code == 200
    assert desktop.put(url, json=project).status_code == 409
    assert phone.put(url, json=draft).status_code == 409
    assert phone.get('/v1/settings').status_code == 404
    assert phone.post('/v1/projects/open', json={'name': '不能打开目录'}).status_code in (404, 405)
    assert phone.get('/v1/mobile').status_code == 404
    assert token not in (gateway.store.home / 'story.sqlite3').read_bytes().decode('latin1')
    assert token not in desktop.get('/v1/mobile').text
    assert desktop.post('/v1/mobile/devices/' + credentials['id'] + '/revoke', json={}).status_code == 200
    assert phone.get('/v1/projects').status_code == 401
    assert phone.post('/pair/' + credentials['id'] + '/poll', json={'secret': credentials['secret']}).status_code == 410


def test_rejection_expiry_and_wrong_poll_secret(mobile):
    desktop, phone, gateway, project = mobile
    qr = desktop.post('/v1/mobile/pair', json={'address': '192.168.1.10'}).json()
    code = parse_qs(urlsplit(qr['url']).fragment)['pair'][0]
    credentials = phone.post('/pair/claim', json={'code': code, 'name': '陌生手机'}).json()
    assert phone.post('/pair/' + credentials['id'] + '/poll', json={'secret': 'x' * 32}).status_code == 410
    desktop.post('/v1/mobile/pending/' + credentials['id'], json={'approve': False})
    assert phone.post('/pair/' + credentials['id'] + '/poll', json={'secret': credentials['secret']}).json()['status'] == 'rejected'
    gateway.pending[credentials['id']]['expires'] = 0
    assert desktop.post('/v1/mobile/pending/' + credentials['id'], json={'approve': True}).status_code == 404
    gateway.codes[hashlib.sha256(code.encode()).hexdigest()] = time.time() - 1
    assert phone.post('/pair/claim', json={'code': code, 'name': '过期'}).status_code == 410
    assert desktop.post('/v1/mobile/pair', json={'address': '8.8.8.8'}).status_code == 422
    assert TestClient(gateway.app, client=('8.8.8.8', 5000)).get('/mobile').status_code == 403
    assert TestClient(desktop.app).get('/v1/mobile').status_code == 401


def test_gateway_disabled_and_static_page(mobile):
    desktop, phone, gateway, project = mobile
    assert phone.get('/mobile').status_code == 200
    assert '/src/mobile.tsx' not in phone.get('/mobile').text
    credentials, token = bind(desktop, phone)
    gateway.stop()
    assert phone.get('/v1/projects').status_code == 503
    assert not gateway.pending
    assert not gateway.codes
    assert desktop.post('/v1/mobile/pair', json={'address': '192.168.1.10'}).status_code == 409


def test_real_listener_lifecycle_and_restart(mobile):
    desktop, phone, gateway, project = mobile
    _, token = bind(desktop, phone)
    gateway.stop()
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    try:
        state = gateway.configure(MobileConfig(enabled=True, port=port))
        assert state['enabled']
        with httpx.Client(trust_env=False) as remote:
            assert remote.get(f'http://127.0.0.1:{port}/mobile').status_code == 200
            assert remote.get(f'http://127.0.0.1:{port}/v1/projects').status_code == 401
            response = remote.get(f'http://127.0.0.1:{port}/v1/projects', headers={'Authorization': 'Bearer ' + token})
            assert response.status_code == 200
        gateway.configure(MobileConfig(enabled=False, port=port))
        assert not gateway.enabled
        assert not gateway.thread
        reloaded = MobileGateway(gateway.store)
        reloaded.enabled = True
        assert reloaded.authenticate('Bearer ' + token)['name'] == '测试手机'
    finally:
        gateway.stop()
