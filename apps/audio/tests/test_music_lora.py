import json
import struct
from unittest.mock import AsyncMock
import pytest
from fastapi.testclient import TestClient
from server.app import create_app
from server.models import MusicRequest
from server.music_lora import catalog, prepare_loras
from fastapi import HTTPException

def header_file(path, prefix):
    header = json.dumps({prefix+'.lora_up.weight':{'dtype':'F32','shape':[2,1],'data_offsets':[0,8]},prefix+'.lora_down.weight':{'dtype':'F32','shape':[1,2],'data_offsets':[8,16]}}).encode()
    path.write_bytes(struct.pack('<Q',len(header))+header+bytes(16))

def test_provider_constraints():
    for params in ({'lora_provider':'starnodes2024','planner_lora':'a.safetensors'}, {'lora_provider':'speedyrulz'}, {'acoustic_lora':'a.safetensors'}, {'lora_provider':'unknown'}, {'acoustic_strength':4}):
        with pytest.raises(ValueError):
            MusicRequest(lyrics='a',style='b',**params)
    assert MusicRequest(lyrics='a',style='b').lora_provider=='none'

def test_catalog_and_bad_headers(tmp_path):
    header_file(tmp_path/'model.safetensors','diffusion_model.model.layers.0.self_attn.o_proj')
    header_file(tmp_path/'planner.safetensors','text_encoders.model.layers.0.self_attn.o_proj')
    (tmp_path/'broken.safetensors').write_bytes(struct.pack('<Q',2**40))
    result = catalog(str(tmp_path))
    assert len(result['providers'])==3
    files = {f['name']:f for f in result['files']}
    assert files['model']['targets']==['acoustic']
    assert files['planner']['targets']==['planner']
    assert files['broken']['error']

def test_lora_scope_and_type(tmp_path):
    root=tmp_path/'loras'; root.mkdir()
    header_file(root/'model.safetensors','diffusion_model.llm2vae')
    for name in ('../outside.safetensors', str(tmp_path/'outside.safetensors'), 'absent.safetensors'):
        with pytest.raises(HTTPException): prepare_loras(str(root),{'acoustic_lora':name})
    with pytest.raises(HTTPException): prepare_loras(str(root),{'planner_lora':'model.safetensors'})
    assert prepare_loras(str(root),{'acoustic_lora':'model.safetensors'})['acoustic_lora_path']==str(root/'model.safetensors')

def test_lora_api_active_config(tmp_path,monkeypatch):
    app=create_app(tmp_path/'app',token='test')
    with TestClient(app) as c:
        c.headers['Authorization']='Bearer test'
        root=tmp_path/'loras'; root.mkdir()
        header_file(root/'model.safetensors','diffusion_model.llm2vae')
        m=app.state.manager
        m.active.music.lora_dir=str(root)
        m.config.music.lora_dir=str(tmp_path/'not-active')
        m.states['music']={'status':'ready','message':'test'}
        submit=AsyncMock(return_value={'id':'lora','status':'queued'})
        monkeypatch.setattr(m,'submit',submit)
        assert c.get('/v1/music/lora-options').json()['directory']==str(root)
        assert c.get('/v1/music/lora-options',headers={'Authorization':''}).status_code==401
        for provider in ('speedyrulz','starnodes2024'):
            response=c.post('/v1/music/generate?wait=false',json={'lyrics':'a','style':'b','lora_provider':provider,'acoustic_lora':'model.safetensors'})
            assert response.status_code==202
            assert submit.call_args.args[1]['acoustic_lora_path']==str(root/'model.safetensors')
