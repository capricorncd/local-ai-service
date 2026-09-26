import asyncio
import hashlib
import io
import json
import sys
from unittest.mock import AsyncMock
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from server.app import create_app
from server.models import TtsRequest
from server.core import Manager
from server.breeze_download import BreezeDownload

def test_tts_model_contract():
    assert TtsRequest(text='hello').model == 'qwen3-tts'
    assert TtsRequest(model='breeze-tts2', text='hello', instruct='warm voice').instruct
    assert TtsRequest(model='breeze-tts2', text='hello', reference_upload_id='x', reference_text='sample', instruct='slowly').reference_text
    for extra in ({'speaker':'vivian'}, {'language':'Japanese'}, {'temperature':.8}, {'max_new_tokens':500}, {'reference_upload_id':'x'}):
        with pytest.raises(ValidationError):
            TtsRequest(model='breeze-tts2',text='hello',instruct='warm',**extra)
    for body in ({'model':'bad','text':'a'}, {'model':'breeze-tts2','text':'a'}, {'text':'a','cfg_scale':4}):
        with pytest.raises(ValidationError): TtsRequest(**body)

def test_unified_routes(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCAL_AI_DESKTOP','1')
    app=create_app(tmp_path,token='test')
    with TestClient(app) as client:
        client.headers['Authorization']='Bearer test'
        submit=AsyncMock(return_value={'id':'tts','status':'queued'})
        monkeypatch.setattr(app.state.manager,'submit',submit)
        # Breeze does not depend on the Qwen readiness state.
        assert client.post('/v1/tts/generate?wait=false',json={'model':'breeze-tts2','text':'hello','instruct':'warm voice'}).status_code==202
        assert submit.call_args.args[1]['model']=='breeze-tts2'
        models=client.get('/v1/tts/models').json()['models']
        assert [m['id'] for m in models]==['qwen3-tts','breeze-tts2']
        assert models[1]['status']=='needs_config'
        assert client.post('/internal/tts/breeze/download').status_code==403
        assert '/internal/tts/breeze/download' not in client.get('/openapi.json').json()['paths']

def test_breeze_queue_shared_runtime(tmp_path,monkeypatch):
    m=Manager(tmp_path)
    monkeypatch.setattr('server.breeze_worker.check_breeze',lambda cfg:[])
    request=TtsRequest(model='breeze-tts2',text='hello',instruct='warm').model_dump()
    asyncio.run(m.submit('tts',request))
    _,name,params,cfg=m.queue.get_nowait()
    assert name=='tts' and cfg['python']==m.active.tts.python
    assert cfg['output_dir']==m.active.tts.breeze_output_dir
    assert params['cfg_scale']==4 and params['speaker'] is None
    assert params['temperature'] is None

def test_download_verify_reuse_cancel(tmp_path,monkeypatch):
    data=b'model-content'
    meta={'sha':'a'*40,'siblings':[{'rfilename':'model.safetensors','size':len(data),'lfs':{'sha256':hashlib.sha256(data).hexdigest()}}]}
    calls=[]
    def response(url,timeout):
        calls.append(url)
        return io.BytesIO(json.dumps(meta).encode() if '/api/models/' in url else data)
    monkeypatch.setattr('server.breeze_download.urlopen',response)
    d=BreezeDownload(tmp_path)
    d.download()
    assert (tmp_path/'model.safetensors').read_bytes()==data
    assert d.state['downloaded']==len(data)
    calls.clear();d.download();assert len(calls)==1
    (tmp_path/'model.safetensors').write_bytes(b'x'*len(data))
    d.download();assert (tmp_path/'model.safetensors').read_bytes()==data
    d.cancelled.set();calls.clear();d.download();assert len(calls)==1

def test_download_rejects_corruption(tmp_path,monkeypatch):
    meta={'sha':'a'*40,'siblings':[{'rfilename':'model.safetensors','size':3,'lfs':{'sha256':'0'*64}}]}
    monkeypatch.setattr('server.breeze_download.urlopen',lambda url,timeout:io.BytesIO(json.dumps(meta).encode() if '/api/models/' in url else b'bad'))
    with pytest.raises(RuntimeError):BreezeDownload(tmp_path).download()
    assert not (tmp_path/'model.safetensors').exists()
