import asyncio
import json
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from server.app import create_app
from server.core import Manager

def test_sfx_migration(tmp_path):
    manager = Manager(tmp_path)
    cfg = manager.config.model_dump()
    cfg.pop('sfx')
    cfg['music']['steps'] = 17
    manager.config_path.write_text(json.dumps(cfg), 'utf-8')
    restored = Manager(tmp_path)
    assert restored.config.music.steps == 17
    assert restored.config.sfx.seconds == 10
    assert restored.config.sfx.output_dir == str(tmp_path / 'sfx')
    assert 'sfx' in json.loads(manager.config_path.read_text('utf-8'))

def test_sfx_api(tmp_path, monkeypatch):
    app = create_app(tmp_path, token='test')
    with TestClient(app) as client:
        client.headers['Authorization'] = 'Bearer test'
        cfg = client.get('/v1/config').json()
        cfg['sfx']['model_dir'] = str(tmp_path / 'missing')
        client.put('/v1/config', json=cfg)
        assert client.post('/v1/services/sfx/restart').json()['status'] == 'needs_config'
        assert client.post('/v1/sfx/generate', json={'prompt':'雨声'}).status_code == 503
        for params in ({'prompt':' '}, {'prompt':'雨','seconds':31}, {'prompt':'雨','count':5}, {'prompt':'雨','sigma_shift':0}, {'prompt':'雨','strength':1}):
            assert client.post('/v1/sfx/generate', json=params).status_code == 422
        assert client.post('/v1/sfx/generate', json={'prompt':'雨'}, headers={'Authorization':''}).status_code == 401
        submit = AsyncMock(return_value={'id':'sfx-test','service':'sfx','status':'queued'})
        monkeypatch.setattr(app.state.manager, 'submit', submit)
        response = client.post('/v1/sfx/generate?wait=false', json={'prompt':'雨声','count':2,'seed':3})
        assert response.status_code == 202
        assert submit.call_args.args[0] == 'sfx'
        assert submit.call_args.args[1]['count'] == 2
        submit.return_value = {'id':'ok','status':'succeeded','result':{'files':[{'url':'/v1/jobs/ok/files/0'}]}}
        assert client.post('/v1/sfx/generate', json={'prompt':'雨'}).json()['files'][0]['url'].endswith('/0')

def test_sfx_uses_active_defaults(tmp_path):
    async def scenario():
        manager = Manager(tmp_path)
        manager.states['sfx'] = {'status':'ready','message':'test'}
        manager.config.sfx.seconds = 15
        job = await manager.submit('sfx', {'prompt':'rain','seconds':None,'num_inference_steps':None,'cfg_scale':None,'sigma_shift':None,'count':None})
        assert job['request']['seconds'] == 10
        assert job['request']['num_inference_steps'] == 100
        assert job['request']['count'] == 1
    asyncio.run(scenario())
