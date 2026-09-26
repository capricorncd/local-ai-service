import json
from unittest.mock import AsyncMock
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from server.app import create_app
from server.core import Manager

@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / 'app', token='test')) as client:
        client.headers['Authorization'] = 'Bearer test'
        yield client

def test_voice_migration(tmp_path):
    m = Manager(tmp_path)
    cfg = m.config.model_dump()
    cfg.pop('tts'); cfg.pop('vc')
    cfg['sfx']['seconds'] = 17
    m.config_path.write_text(json.dumps(cfg), 'utf-8')
    restored = Manager(tmp_path)
    assert restored.config.sfx.seconds == 17
    assert restored.config.tts.output_dir == str(tmp_path / 'tts')
    assert restored.config.vc.output_dir == str(tmp_path / 'vc')

def test_presets_and_preview(client, tmp_path):
    m = client.app.state.manager
    m.active.vc.voices_dir = str(tmp_path)
    (tmp_path/'vivian.wav').write_bytes(b'RIFF-test')
    voices = client.get('/v1/voices').json()
    assert len(voices) == 9
    assert voices[0]['vc_available']
    assert not voices[1]['vc_available']
    assert client.get(voices[0]['preview_url']).content == b'RIFF-test'
    assert client.get('/v1/voices/unknown/audio').status_code == 404
    assert client.get('/v1/voices/serena/audio').status_code == 503
    assert client.get('/v1/voices', headers={'Authorization':''}).status_code == 401

def test_tts_routes(client, monkeypatch):
    m = client.app.state.manager
    m.states['tts'] = {'status':'ready','message':'test'}
    submit = AsyncMock(return_value={'id':'tts','status':'queued'})
    monkeypatch.setattr(m,'submit',submit)
    assert client.post('/v1/tts/generate?wait=false', json={'text':'你好','speaker':'serena'}).status_code == 202
    assert submit.call_args.args[0] == 'tts'
    uploaded = client.post('/v1/uploads', files={'file':('ref.wav',b'RIFF')}).json()['upload_id']
    assert client.post('/v1/tts/generate?wait=false', json={'text':'你好','reference_upload_id':uploaded,'reference_text':'原文'}).status_code == 202
    assert Path(submit.call_args.args[1]['reference_path']).name == uploaded
    for body in ({'text':' '},{'text':'a','speaker':'bad'},{'text':'a','reference_upload_id':uploaded,'speaker':'vivian'},{'text':'a','reference_upload_id':uploaded,'instruct':'快乐'},{'text':'a','reference_text':'孤立原文'}):
        assert client.post('/v1/tts/generate', json=body).status_code == 422
    assert client.post('/v1/tts/generate', json={'text':'a','reference_upload_id':'../config.json'}).status_code == 404
    assert client.post('/v1/tts/generate', json={'text':'a'}, headers={'Authorization':''}).status_code == 401

def test_vc_routes(client, monkeypatch, tmp_path):
    m = client.app.state.manager
    m.states['vc'] = {'status':'ready','message':'test'}
    m.active.vc.voices_dir = str(tmp_path)
    (tmp_path/'vivian.wav').write_bytes(b'RIFF')
    submit = AsyncMock(return_value={'id':'vc','status':'queued'})
    monkeypatch.setattr(m,'submit',submit)
    uploaded = client.post('/v1/uploads', files={'file':('source.wav',b'RIFF')}).json()['upload_id']
    for target in ({'target_voice':'vivian'}, {'reference_upload_id':uploaded}):
        response = client.post('/v1/voice/convert?wait=false', json={'source_upload_id':uploaded,**target})
        assert response.status_code == 202
        assert submit.call_args.args[0] == 'vc'
        assert Path(submit.call_args.args[1]['reference_path']).is_file()
    assert client.post('/v1/voice/convert', json={'source_upload_id':uploaded}).status_code == 422
    assert client.post('/v1/voice/convert', json={'source_upload_id':uploaded,'reference_upload_id':uploaded,'target_voice':'vivian'}).status_code == 422
    assert client.post('/v1/voice/convert', json={'source_upload_id':'../config.json','target_voice':'vivian'}).status_code == 404
    assert client.post('/v1/voice/convert', json={'source_upload_id':uploaded,'target_voice':'serena'}).status_code == 503

def test_voice_missing_models_independent(client):
    cfg = client.get('/v1/config').json()
    original = client.get('/v1/status').json()['services']['sfx']
    cfg['vc']['model_dir'] = 'nonexistent'
    cfg['tts']['model_dir'] = 'nonexistent'
    assert client.put('/v1/config',json=cfg).status_code == 200
    for name in ('tts','vc'):
        assert client.post(f'/v1/services/{name}/restart').json()['status'] == 'needs_config'
    assert client.get('/v1/status').json()['services']['sfx'] == original
    assert client.post('/v1/tts/generate',json={'text':'你好'}).status_code == 503
