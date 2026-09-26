import base64
import io
import json
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
from app import create_app
from domain import Generate, Config, inspect_models, build_prompt

@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app) as c:
        c.headers['Authorization'] = 'Bearer ' + (tmp_path / 'api-token').read_text()
        yield c

def png():
    b = io.BytesIO()
    Image.new('RGBA',(32,32),(1,2,3,128)).save(b,format='PNG')
    return b.getvalue()

def test_mode_contracts():
    for mode in ('continue','extract','fidelity','brush','circle','mask','alpha','multi'):
        with pytest.raises(ValidationError):
            Generate(mode=mode,prompt='edit')
    with pytest.raises(ValidationError):
        Generate(prompt='   ')
    with pytest.raises(ValidationError):
        Generate(prompt='test',width=2048,height=2048)
    with pytest.raises(ValidationError):
        Generate(prompt='test',references=['a']*11)
    req=Generate(mode='mask',prompt='make it blue',references=['a'],mask='b')
    assert 'white' in build_prompt(req) and build_prompt(req).endswith('make it blue')

def test_auth_and_upload(client):
    assert client.get('/v1/jobs',headers={'Authorization':'wrong'}).status_code==401
    bad=client.post('/v1/images',files={'file':('x.png',b'not an image')})
    assert bad.status_code==400
    r=client.post('/v1/images',files={'file':('x.png',png())})
    assert r.status_code==200
    image=client.get('/v1/images/'+r.json()['id'])
    assert image.status_code==200
    with Image.open(io.BytesIO(image.content)) as im:
        assert im.getpixel((0,0))==(1,2,3,128)
    assert client.get('/v1/images/not-a-valid-id').status_code==404

def test_project_roundtrip(client):
    data='data:image/png;base64,'+base64.b64encode(png()).decode()
    project={'format':'local-ai-image','version':1,'name':'日本語 中文','width':1024,'height':1024,
             'layers':[{'id':'a','name':'layer','source':data,'width':32,'height':32,'x':5,'y':-4,'scale':2,'opacity':.5,'visible':True,'locked':True,'reference':False}],
             'active':'a','mask':data,'prompt':'hello','negative':'','mode':'brush','steps':30,'cfg':4,'seed':-1}
    r=client.post('/v1/projects',json=project)
    assert r.status_code==201,r.text
    id=r.json()['id']
    assert client.get('/v1/projects/'+id).json()==project
    project['name']='changed'
    assert client.put('/v1/projects/'+id,json=project).status_code==200
    assert client.get('/v1/projects').json()[0]['name']=='changed'
    assert client.get('/v1/projects/'+id).json()['layers'][0]['source']==data
    project['version']=100
    assert client.post('/v1/projects',json=project).status_code==422

def test_missing_models_and_cancel_unknown(client,tmp_path):
    cfg=Config(model_dir=str(tmp_path/'missing')).model_dump()
    assert client.put('/v1/config',json=cfg).status_code==200
    assert client.post('/v1/jobs',json={'prompt':'a flower'}).status_code==409
    assert client.post('/v1/jobs/unknown/cancel').status_code==404

def test_restart_marks_interrupted_jobs(tmp_path):
    import sqlite3
    app=create_app(tmp_path)
    with sqlite3.connect(tmp_path/'images.sqlite3') as db:
        db.execute('INSERT INTO jobs(id,created,status,request) VALUES(?,?,?,?)',('job',1,'running','{}'))
    create_app(tmp_path)
    with sqlite3.connect(tmp_path/'images.sqlite3') as db:
        assert db.execute('SELECT status FROM jobs').fetchone()[0]=='failed'

def test_generate_project_uses_only_enabled_visible_layers(client,tmp_path,monkeypatch):
    import app as module
    import time
    import subprocess
    captured=[]
    core=tmp_path/'core/comfy/text_encoders'
    core.mkdir(parents=True)
    (core/'qwen_image21.py').write_text('')
    cfg=Config(python=sys.executable,core=str(tmp_path/'core')).model_dump()
    client.put('/v1/config',json=cfg)
    monkeypatch.setattr(module,'inspect_models',lambda _:[])
    class FakeWorker:
        returncode=0
        def __init__(self,args,**kwargs):
            payload=json.loads(Path(args[-1]).read_text('utf-8'))
            captured.append(payload)
            Path(payload['output']).write_bytes(png())
        def poll(self): return 0
    monkeypatch.setattr(subprocess,'Popen',FakeWorker)
    data='data:image/png;base64,'+base64.b64encode(png()).decode()
    layer={'id':'a','name':'a','source':data,'width':32,'height':32,'x':16,'y':16,'scale':1,'opacity':.5,'visible':True,'locked':False,'reference':True}
    project={'format':'local-ai-image','version':1,'name':'test','width':256,'height':256,
        'layers':[layer,{**layer,'id':'hidden','visible':False},{**layer,'id':'excluded','reference':False}],
        'active':'a','mask':None,'prompt':'edit','negative':'','mode':'continue','steps':1,'cfg':1,'seed':-1}
    id=client.post('/v1/projects',json=project).json()['id']
    response=client.post('/v1/projects/'+id+'/generate')
    assert response.status_code==202,response.text
    job=response.json()['id']
    for _ in range(30):
        state=client.get('/v1/jobs/'+job).json()
        if state['status'] in ('failed','completed'):break
        time.sleep(.01)
    assert state['status']=='completed',state
    assert 0<=state['request']['seed']<2**32
    assert len(captured[0]['references'])==1
    with Image.open(captured[0]['references'][0]) as im:
        assert im.size==(256,256)
        assert im.getpixel((0,0))[3]==0
        assert im.getpixel((20,20))[3]==64
    assert client.get('/v1/jobs/'+job+'/image').status_code==200
    assert client.post('/v1/jobs/'+job+'/reference').status_code==200


def test_model_paths_require_explicit_selection(tmp_path, monkeypatch):
    import struct
    header=json.dumps({'weight': {'dtype': 'F32', 'shape': [1], 'data_offsets': [0, 4]}}).encode()
    for name in ('qwen_image_2.1_bf16.safetensors', 'qwen_image_2.1_vae_bf16.safetensors', 'qwen3vl_8b_bf16.safetensors'):
        (tmp_path/name).write_bytes(struct.pack('<Q', len(header))+header+bytes(4))
    monkeypatch.chdir(tmp_path)
    assert all(not row['ready'] for row in inspect_models(Config()))
    assert all(row['ready'] for row in inspect_models(Config(model_dir=str(tmp_path))))
    selected=Config(**{key: str(tmp_path/name) for key,name in {
        'model': 'qwen_image_2.1_bf16.safetensors', 'vae': 'qwen_image_2.1_vae_bf16.safetensors', 'encoder': 'qwen3vl_8b_bf16.safetensors'
    }.items()})
    assert all(row['ready'] for row in inspect_models(selected))
