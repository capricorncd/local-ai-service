import asyncio
import json
import sys
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from server.app import create_app
from server.core import Manager, connect

@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / 'app', token='test-secret')
    with TestClient(app) as client:
        client.headers['Authorization'] = 'Bearer test-secret'
        yield client

def setup_library(client, tmp_path):
    library = tmp_path / 'sounds'
    (library / '自然').mkdir(parents=True)
    (library / '自然' / '雨.wav').write_bytes(b'RIFF-test-sound')
    (library / '未分类.mp3').write_bytes(b'ID3-test')
    (library / 'private.txt').write_text('must not be indexed')
    cfg = client.get('/v1/config').json()
    cfg['library']['directory'] = str(library)
    assert client.put('/v1/config', json=cfg).status_code == 200
    assert client.post('/v1/services/library/restart').json()['status'] == 'ready'
    return library

def test_auth_and_health(client):
    assert client.get('/health').status_code == 200
    assert client.get('/v1/config', headers={'Authorization': ''}).status_code == 401
    assert client.get('/v1/status', headers={'Authorization': 'Bearer wrong'}).status_code == 401

def test_invalid_config_and_restart(client):
    config = client.get('/v1/config').json()
    config['music']['steps'] = -1
    assert client.put('/v1/config', json=config).status_code == 422
    config['music']['steps'] = 20
    config['music']['enabled'] = False
    assert client.put('/v1/config', json=config).status_code == 200
    assert client.get('/v1/status').json()['services']['music']['pending_restart']
    assert client.post('/v1/services/music/restart').json()['status'] == 'stopped'
    assert not client.get('/v1/status').json()['services']['music']['pending_restart']
    assert client.post('/v1/services/unknown/restart').status_code == 404

def test_music_validation_and_unavailable(client):
    assert client.post('/v1/music/generate', json={'lyrics':'a','style':'b','count':3}).status_code == 422
    config = client.get('/v1/config').json()
    config['music']['enabled'] = False
    client.put('/v1/config', json=config)
    client.post('/v1/services/music/restart')
    assert client.post('/v1/music/generate', json={'lyrics':'a','style':'b'}).status_code == 503

def test_library_index_filter_download_and_prune(client, tmp_path):
    root = setup_library(client, tmp_path)
    assert client.post('/v1/sounds/scan').json()['count'] == 2
    assert client.post('/v1/sounds/scan').json()['count'] == 2
    items = client.get('/v1/sounds', params={'category':'自然'}).json()
    assert items['total'] == 1
    assert items['items'][0]['name'] == '雨.wav'
    url = items['items'][0]['url']
    assert client.get(url).content == b'RIFF-test-sound'
    assert client.get(url, headers={'Range':'bytes=0-3'}).status_code == 206
    assert client.get('/v1/sounds', params={'q':"' OR 1=1 --"}).json()['total'] == 0
    assert client.get('/v1/sounds?limit=500').status_code == 422
    (root / '自然' / '雨.wav').unlink()
    assert client.get(url).status_code == 404
    assert client.post('/v1/sounds/scan').json()['count'] == 1
    assert client.get('/v1/categories').json() == [{'category':'未分类','count':1}]

def test_library_blocks_database_path_escape(client, tmp_path):
    root = setup_library(client, tmp_path)
    secret = tmp_path / 'secret.wav'
    secret.write_bytes(b'secret')
    database = client.get('/v1/config').json()['library']['database']
    with connect(database) as db:
        db.execute('INSERT INTO sounds VALUES (?,?,?,?,?,?,?)', ('escape',str(root.resolve()),'../secret.wav','secret','x',6,0))
    assert client.get('/v1/sounds/escape/audio').status_code == 404

def test_upload_and_traversal(client):
    assert client.post('/v1/uploads', files={'file':('x.exe',b'test')}).status_code == 415
    assert client.post('/v1/uploads', files={'file':('x.wav',b'')}).status_code == 400
    uploaded = client.post('/v1/uploads', files={'file':('../../x.wav',b'RIFF')})
    assert uploaded.status_code == 200
    assert '/' not in uploaded.json()['upload_id']
    assert client.post('/v1/denoise', json={'upload_id':'../config.json'}).status_code == 404

def test_crash_recovery(tmp_path):
    manager = Manager(tmp_path)
    with connect(manager.db_path) as db:
        db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,NULL,NULL)',('crash','music','running',0,0,'{}'))
    restored = Manager(tmp_path)
    assert restored.job('crash')['status'] == 'failed'

def test_separation_migrates_old_config_without_changing_denoise(tmp_path):
    manager = Manager(tmp_path)
    old = manager.config.model_dump()
    old.pop('separation')
    old['denoise']['segment_seconds'] = 24
    manager.config_path.write_text(json.dumps(old), 'utf-8')
    migrated = Manager(tmp_path)
    assert migrated.config.denoise.segment_seconds == 24
    assert migrated.config.separation.segment_seconds == 2
    assert migrated.config.separation.output_dir == str(tmp_path.resolve() / 'separation')
    assert 'separation' in json.loads(manager.config_path.read_text('utf-8'))

def test_separation_is_independent(client):
    cfg = client.get('/v1/config').json()
    cfg['separation']['model_dir'] = 'not-a-model-directory'
    original_denoise = client.get('/v1/status').json()['services']['denoise']
    assert client.put('/v1/config', json=cfg).status_code == 200
    assert client.post('/v1/services/separation/restart').json()['status'] == 'needs_config'
    assert client.get('/v1/status').json()['services']['denoise'] == original_denoise
    assert client.post('/v1/separate/file', files={'file':('x.wav',b'RIFF')}).status_code == 503

def test_separation_endpoints_and_validation(client, monkeypatch):
    from unittest.mock import AsyncMock
    manager = client.app.state.manager
    manager.states['separation'] = {'status':'ready','message':'test'}
    submit = AsyncMock(return_value={'id':'test-separation','service':'separation','status':'queued'})
    monkeypatch.setattr(manager, 'submit', submit)
    file = client.post('/v1/uploads', files={'file':('two.wav',b'RIFF')}).json()
    response = client.post('/v1/separate?wait=false', json={'upload_id':file['upload_id'],'segment_seconds':2})
    assert response.status_code == 202
    args = submit.call_args.args
    assert args[0] == 'separation' and args[1]['segment_seconds'] == 2
    response = client.post('/v1/separate/file?wait=false', files={'file':('two.mp4',b'video')}, data={'segment_seconds':3,'max_duration':60})
    assert response.status_code == 202
    assert submit.call_args.args[1]['max_duration'] == 60
    assert client.post('/v1/separate', json={'upload_id':file['upload_id'],'segment_seconds':1}).status_code == 422
    assert client.post('/v1/separate/file', files={'file':('two.wav',b'RIFF')}, data={'segment_seconds':1}).status_code == 422
    assert client.post('/v1/separate', json={'upload_id':'../config.json'}).status_code == 404
    assert client.post('/v1/separate', json={'upload_id':file['upload_id'],'speakers':3}).status_code == 422
    assert client.post('/v1/separate', json={'upload_id':file['upload_id']}, headers={'Authorization':''}).status_code == 401

def test_worker_queue_failure_and_shutdown(tmp_path):
    async def scenario():
        manager = Manager(tmp_path)
        cfg = manager.active.music
        cfg.python = sys.executable
        cfg.model_path = 'missing.safetensors'
        manager.states['music'] = {'status':'ready','message':'test adapter'}
        request = {'lyrics':'test','style':'test','seed':1}
        first = await manager.submit('music', request.copy())
        second = await manager.submit('music', request.copy())
        await manager.cancel(second['id'])
        manager.worker_task = asyncio.create_task(manager.work())
        await asyncio.wait_for(manager.queue.join(), 20)
        assert manager.job(first['id'])['status'] == 'failed'
        assert manager.job(second['id'])['status'] == 'cancelled'
        assert manager.process is None
        await manager.close()
    asyncio.run(scenario())

def test_restart_rejects_queued_jobs(tmp_path):
    async def scenario():
        manager = Manager(tmp_path)
        manager.states['music'] = {'status':'ready','message':'test'}
        await manager.submit('music', {'lyrics':'a','style':'b'})
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as error:
            await manager.restart('music')
        assert error.value.status_code == 409
    asyncio.run(scenario())

def test_windows_job_object_cleans_descendants(tmp_path):
    import os
    import subprocess
    if os.name != 'nt':
        pytest.skip('Windows process tree isolation')
    from server.process_tree import ProcessTree
    marker = tmp_path / 'child.pid'
    code = "import subprocess,sys,time,pathlib; time.sleep(1); p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); pathlib.Path(sys.argv[1]).write_text(str(p.pid)); time.sleep(60)"
    parent = subprocess.Popen([sys.executable, '-c', code, str(marker)], creationflags=subprocess.CREATE_NO_WINDOW)
    tree = ProcessTree(parent.pid)
    try:
        deadline = time.monotonic() + 5
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(.05)
        assert marker.exists()
        child_pid = int(marker.read_text())
        tree.close()
        parent.wait(timeout=5)
        import ctypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x1000, False, child_pid)
        if handle:
            exit_code = ctypes.c_ulong()
            try:
                assert kernel.GetExitCodeProcess(handle, ctypes.byref(exit_code))
                assert exit_code.value != 259  # STILL_ACTIVE
            finally:
                kernel.CloseHandle(handle)
    finally:
        tree.close()
        if parent.poll() is None:
            parent.kill()
        parent.wait(timeout=5)


def test_music_score_option_and_download(client, tmp_path, monkeypatch):
    from unittest.mock import AsyncMock
    manager = client.app.state.manager
    manager.states['music'] = {'status':'ready','message':'test'}
    submit = AsyncMock(return_value={'id':'score-test','status':'queued'})
    monkeypatch.setattr(manager, 'submit', submit)
    payload = {'lyrics':'test','style':'pop'}
    assert client.post('/v1/music/generate?wait=false', json=payload).status_code == 202
    assert submit.call_args.args[1]['generate_score'] is False
    for mode in ('full', 'melody'):
        assert client.post('/v1/music/generate?wait=false', json={**payload,'generate_score':True,'mode':mode}).status_code == 202
        assert submit.call_args.args[1]['generate_score'] is True
    assert client.post('/v1/music/generate', json={**payload,'generate_score':True,'mode':'off'}).status_code == 422
    score = tmp_path / 'song-1.abc'
    abc = 'X:1\nT:测试\nM:4/4\nK:C\nCDEF GABc|'
    score.write_text(abc, 'utf-8')
    result = {'files':[], 'scores':[{'path':str(score),'audio_index':0,'mode':'full'}]}
    with connect(manager.db_path) as db:
        db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?,NULL)', ('score-test','music','succeeded',0,0,'{}',json.dumps(result)))
    url = '/v1/jobs/score-test/scores/0'
    assert client.get(url).json()['abc'] == abc
    response = client.get(url+'?download=true')
    assert response.content == score.read_bytes()
    assert 'attachment' in response.headers['content-disposition']
    assert client.get(url, headers={'Authorization':''}).status_code == 401
    assert client.get('/v1/jobs/score-test/scores/-1').status_code == 404
    assert client.get('/v1/jobs/score-test/scores/1').status_code == 404
    score.unlink()
    assert client.get(url).status_code == 404


def test_edited_score_is_desktop_only(client):
    base = {'lyrics':'test','style':'pop','abc':'X:1\nK:C\nCDEF|'}
    assert client.post('/v1/music/generate', json=base).status_code == 422
    assert client.post('/internal/music/regenerate', json={'job_id':'a','score_index':0,'abc':base['abc']}).status_code == 403
    schema = client.get('/openapi.json').json()
    assert '/internal/music/regenerate' not in schema['paths']
    assert 'abc' not in schema['components']['schemas']['MusicRequest']['properties']


def test_desktop_score_reuses_original_parameters(tmp_path, monkeypatch):
    from unittest.mock import AsyncMock
    monkeypatch.setenv('LOCAL_AI_DESKTOP','1')
    app = create_app(tmp_path, token='public-key')
    with TestClient(app) as client:
        manager = app.state.manager
        original = {'lyrics':'hello','style':'pop','seed':10,'count':2,'lora_provider':'speedyrulz','planner_lora':'old.safetensors','planner_lora_path':'private-path','max_duration':15}
        result = {'files':[], 'scores':[{'audio_index':1,'mode':'full'}]}
        with connect(manager.db_path) as db:
            db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?,NULL)', ('original','music','succeeded',0,0,json.dumps(original),json.dumps(result)))
        submit = AsyncMock(return_value={'id':'new','status':'queued'})
        monkeypatch.setattr(manager, 'submit', submit)
        payload = {'job_id':'original','score_index':0,'abc':'X:1\nK:C\nCDEF|'}
        url = '/internal/music/regenerate'
        assert client.post(url,json=payload,headers={'Authorization':'Bearer public-key'}).status_code == 403
        client.headers['X-Desktop-Key'] = (tmp_path / 'desktop-token').read_text()
        assert client.post(url,json=payload).status_code == 202
        params = submit.call_args.args[1]
        assert params['abc'] == payload['abc'] and params['generate_score']
        assert params['seed'] == 11 and params['count'] == 1 and params['max_duration'] == 15
        assert params['lora_provider'] == 'none' and params['planner_lora'] is None
        assert 'planner_lora_path' not in params
        assert client.post(url,json={**payload,'abc':'bad'}).status_code == 422
        assert client.post(url,json={**payload,'score_index':2}).status_code == 404


def test_song_metadata_survives_completion(client):
    manager = client.app.state.manager
    with connect(manager.db_path) as db:
        db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,NULL,NULL)', ('songs','music','queued',0,0,json.dumps({'count':2})))
    url='/v1/music/jobs/songs/songs/1'
    assert client.put(url,json={'title':'  新歌  ','group':'  专辑  '}).status_code == 200
    manager.update('songs','succeeded',result={'files':[{'title':'a'},{'title':'b'}],'scores':[{'audio_index':1}]})
    job=client.get('/v1/jobs/songs').json()
    assert job['result']['files'][1]['title']=='新歌'
    assert job['result']['scores'][0]['title']=='新歌'
    assert job['song_metadata']['1']['group']=='专辑'
    assert client.put(url,json={'title':'   ','group':''}).status_code==422
    assert client.put('/v1/music/jobs/songs/songs/2',json={'title':'x','group':''}).status_code==404
    assert client.put(url,json={'title':'新歌','group':''}).json()['song_metadata']['1']['group']==''
    assert client.put(url,json={'title':'x','group':''},headers={'Authorization':''}).status_code==401


def test_music_naming():
    import re
    from server.music_names import song_titles, song_filename
    titles=song_titles(' ',2)
    assert re.fullmatch(r'\d{8}-\d{6}_1',titles[0])
    assert titles[1]==titles[0][:-1]+'2'
    assert song_titles(' 我的歌 ',1)==['我的歌']
    assert song_titles('我的歌',2)==['我的歌_1','我的歌_2']
    assert '/' not in song_filename('../歌曲:1')
    assert song_filename('CON')=='_CON'


def test_desktop_variation_references_and_isolation(tmp_path, monkeypatch):
    from unittest.mock import AsyncMock
    monkeypatch.setenv('LOCAL_AI_DESKTOP','1')
    app=create_app(tmp_path,token='public')
    with TestClient(app) as client:
        manager=app.state.manager
        manager.states['music']={'status':'ready','message':'test'}
        audio=tmp_path/'song.wav';audio.write_bytes(b'RIFF')
        score=tmp_path/'song.abc';score.write_text('X:1\nK:C\nCDEF|')
        encoder=tmp_path/'encoder.safetensors';encoder.write_bytes(b'test')
        manager.active.music.encoder_path=str(encoder)
        result={'files':[{'path':str(audio)}],'scores':[{'path':str(score),'audio_index':0}]}
        with connect(manager.db_path) as db:
            db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?,NULL)',('source','music','succeeded',0,0,'{}',json.dumps(result)))
        submit=AsyncMock(return_value={'id':'new','status':'queued'})
        monkeypatch.setattr(manager,'submit',submit)
        payload={'job_id':'source','audio_index':0,'reference':'audio','music':{'lyrics':'changed words','style':'jazz','mode':'melody'}}
        url='/internal/music/variation'
        assert client.post(url,json=payload,headers={'Authorization':'Bearer public'}).status_code==403
        client.headers['X-Desktop-Key']=(tmp_path/'desktop-token').read_text()
        assert client.post(url,json=payload).status_code==202
        params=submit.call_args.args[1]
        assert params['reference_audio_path']==str(audio) and params['lyrics']=='changed words'
        assert params['style']=='jazz' and params['source_job_id']=='source'
        blank_style = {**payload, 'music': {**payload['music'], 'style': ' '}}
        assert client.post(url, json=blank_style).status_code == 202
        assert submit.call_args.args[1]['style'] == ''
        with connect(manager.db_path) as db:
            db.execute('UPDATE jobs SET request=? WHERE id=?', (json.dumps({'style': 'acoustic folk'}), 'source'))
        assert client.post(url, json=blank_style).status_code == 202
        assert submit.call_args.args[1]['style'] == ''
        payload['reference']='score';payload['abc']='X:1\nK:D\nDEFG|'
        assert client.post(url,json=payload).status_code==202
        assert submit.call_args.args[1]['abc']==payload['abc']
        assert 'reference_audio_path' not in submit.call_args.args[1]
        assert client.post(url,json={**payload,'audio_index':3}).status_code==404
        payload['music']['mode']='off'
        assert client.post(url,json=payload).status_code==422
        assert url not in client.get('/openapi.json').json()['paths']


def test_uploaded_music_reference(tmp_path, monkeypatch):
    from unittest.mock import AsyncMock
    monkeypatch.setenv('LOCAL_AI_DESKTOP', '1')
    app = create_app(tmp_path, token='public')
    with TestClient(app) as client:
        manager = app.state.manager
        manager.states['music'] = {'status': 'ready', 'message': 'test'}
        encoder = tmp_path / 'encoder.safetensors'
        encoder.write_bytes(b'test')
        manager.active.music.encoder_path = str(encoder)
        client.headers['Authorization'] = 'Bearer public'
        upload_id = client.post('/v1/uploads', files={'file': ('reference.mp3', b'audio')}).json()['upload_id']
        payload = {'upload_id': upload_id, 'music': {'lyrics': 'new lyrics', 'style': 'jazz', 'mode': 'melody'}}
        url = '/internal/music/reference'
        assert client.post(url, json=payload).status_code == 403
        client.headers['X-Desktop-Key'] = (tmp_path / 'desktop-token').read_text()
        submit = AsyncMock(return_value={'id': 'new', 'status': 'queued'})
        monkeypatch.setattr(manager, 'submit', submit)
        assert client.post(url, json=payload).status_code == 202
        params = submit.call_args.args[1]
        assert Path(params['reference_audio_path']).read_bytes() == b'audio'
        assert params['lyrics'] == 'new lyrics' and params['mode'] == 'melody'
        assert client.post(url, json={**payload, 'music': {'style': '', 'lyrics': ''}}).status_code == 202
        assert submit.call_args.args[1]['lyrics'] == '[Instrumental]'
        assert submit.call_args.args[1]['style'].startswith('Instrumental only')
        assert client.post(url, json={**payload, 'music': {'style': '', 'lyrics': 'hello'}}).status_code == 202
        assert submit.call_args.args[1]['style'] == ''
        for extension in ('mp4', 'mov', 'mkv', 'webm', 'avi'):
            video_id = client.post('/v1/uploads', files={'file': (f'reference.{extension}', b'video')}).json()['upload_id']
            assert client.post(url, json={**payload, 'upload_id': video_id}).status_code == 202
            assert Path(submit.call_args.args[1]['reference_audio_path']).suffix == f'.{extension}'
        assert client.post(url, json={**payload, 'upload_id': '../encoder.safetensors'}).status_code == 404
        assert client.post(url, json={**payload, 'music': {**payload['music'], 'mode': 'off'}}).status_code == 422
        encoder.unlink()
        assert client.post(url, json=payload).status_code == 409
        assert url not in client.get('/openapi.json').json()['paths']


def test_auk_requests_and_missing_models(client, monkeypatch):
    from unittest.mock import AsyncMock
    from server.models import AukRequest
    from pydantic import ValidationError
    for payload in ({'task':'lyrics','instruction':'edit'}, {'instruction':'   '}, {'instruction':'edit','upload_id':'x','clip_seconds':20,'gen_seconds':15}):
        with pytest.raises(ValidationError):
            AukRequest(**payload)
    cfg=client.get('/v1/config').json()
    assert cfg['auk']['output_dir']
    assert client.post('/v1/services/auk/restart').json()['status']=='needs_config'
    assert client.post('/v1/audio/edit',json={'task':'tts','instruction':'say hello'}).status_code==503
    uploaded=client.post('/v1/uploads',files={'file':('test.wav',b'RIFF')}).json()['upload_id']
    submit=AsyncMock(return_value={'id':'edit','status':'queued'})
    monkeypatch.setattr(client.app.state.manager,'submit',submit)
    response=client.post('/v1/audio/edit?wait=false',json={'task':'enhance','instruction':'remove noise','upload_id':uploaded})
    assert response.status_code==202 and submit.call_args.args[0]=='auk'
    assert Path(submit.call_args.args[1]['input_path']).is_file()
    assert client.post('/v1/audio/edit',json={'task':'tts','instruction':'hello'},headers={'Authorization':''}).status_code==401
    assert client.post('/v1/audio/edit',json={'task':'enhance','instruction':'edit','upload_id':'../secret'}).status_code==404
