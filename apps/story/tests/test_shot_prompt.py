import io
import json
import sys
from pathlib import Path
import httpx
from PIL import Image
from fastapi.testclient import TestClient
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'server'))
from app import create_app
from domain import Asset, Shot, Project
from shot_prompt import compile_shot_prompt, PREFIXES
import image_metadata


def test_numbered_id_binding_scoped_constraints_preview_and_exact_metadata(tmp_path, monkeypatch):
    app = create_app(tmp_path / 'home')
    store = app.state.store
    with TestClient(app) as client:
        client.headers['Authorization'] = 'Bearer ' + (tmp_path / 'home' / 'api-token').read_text()
        project = client.post('/v1/projects/open', json={'name': '提示词测试'}).json()
        root = store.root(project['id'])
        assets = [
            Asset(name='车厢空景',kind='scene',description='蓝色座椅、银色扶杆。适合透坐下放背包。',constraints='透固定坐在长椅；背包竖放在双腿之间；车厢结构保持一致；场景参考图本身不含人物'),
            Asset(name='玲奈3DCGI人物设定',description='玲奈，成年女性，深色短发，黑白连衣裙。',constraints='酒红色瞳孔保持一致；人物设定图不携带手提包'),
            Asset(name='手提包',kind='prop',description='黑色皮革手提包',constraints='银色新月扣'),
            Asset(name='背景路人多人设定',description='成年乘客，服装颜色不同',constraints='仅作路人群体参考，不作为主要角色身份'),
            Asset(name='无图男主',description='金色短发，黑色夹克'),
        ]
        for asset in assets[:4]:
            asset.image='media/'+asset.id+'.png'
            Image.new('RGB',(32,32),'white').save(root/asset.image)
        metadata={'schema_version':1,'asset_name':'旧名','asset_type':'character','generation_prompt':None,'generation_prompt_status':'unavailable','generation_prompt_source':'test','generation_mode':'unknown','reference_images':[],'setting_description':'过期粉色长发','consistency_constraints':['过期约束']}
        image_metadata.write(root/assets[1].image,metadata,root/'backup')
        # Explicit ID must work despite a stale display name; missing asset_ids is repaired in the request only.
        shot=Shot(title='车门旁',scene='',description=f'@[旧名](asset:{assets[1].id})站在门边，提着@[手提包](asset:{assets[2].id})。@无图男主在前方。',asset_ids=[a.id for a in assets[:4]])
        project['assets']=[a.model_dump() for a in assets]
        project['chapters'][0]['episodes'][0]['shots']=[shot.model_dump()]
        base='/v1/projects/'+project['id']
        project=client.put(base,json=project).json()
        request={'kind':'shot','target_id':shot.id}
        preview=client.post(base+'/generation-preview',json=request)
        assert preview.status_code==200,preview.text
        plan=preview.json();prompt=plan['prompt']
        assert '角色A（参考图2 / image 2）站在门边' in prompt
        assert '道具1（参考图3 / image 3）' in prompt
        assert '背景人物1' in prompt
        assert '角色B（文字设定，无参考图）' in prompt
        assert '3DCGI人物设定' not in prompt and '@[' not in prompt
        assert '透固定坐在' not in prompt and '背包竖放' not in prompt
        assert '人物设定图不携带手提包' not in prompt
        assert '酒红色瞳孔保持一致' in prompt and '过期粉色长发' not in prompt
        assert plan['mode']=='multi'
        assert any('占位文字' in warning for warning in plan['warnings'])
        assert plan['references'][0]['excluded']
        assert client.get(base).json()==project
        client.put('/v1/settings',json={'image_token':'test'})
        submitted={};uploads=[]
        png=io.BytesIO();Image.new('RGB',(32,32),'white').save(png,format='PNG')
        def handle(req):
            if req.url.path=='/v1/images':
                uploads.append(req.content);return httpx.Response(200,json={'id':str(len(uploads))})
            if req.method=='POST' and req.url.path=='/v1/jobs':
                submitted.update(json.loads(req.content));return httpx.Response(200,json={'id':'result','status':'queued'})
            if req.url.path.endswith('/image'):return httpx.Response(200,content=png.getvalue())
            return httpx.Response(200,json={'status':'completed','progress':100})
        original=httpx.Client
        monkeypatch.setattr('app.httpx.Client',lambda **kwargs:original(transport=httpx.MockTransport(handle),**kwargs))
        edited=prompt+'\n三个主体不要完全遮挡。'
        generated=client.post(base+'/generate',json={**request,'prompt_override':edited,'revision':plan['revision']})
        assert generated.status_code==200,generated.text
        job=generated.json()
        assert submitted['mode']=='multi' and submitted['references']==['1','2','3','4']
        assert submitted['prompt']==edited
        for content,asset in zip(uploads,assets):assert (asset.id+'.png').encode() in content
        done=client.get(base+'/jobs/'+job['id']).json()
        record=image_metadata.read(store.media(project['id'],done['path']))
        assert record['generation_prompt']==PREFIXES['multi']+'\n'+edited
        assert image_metadata.image_digest(store.media(project['id'],done['path']).read_bytes())==image_metadata.image_digest(png.getvalue())
        assert client.post(base+'/generate',json={**request,'revision':0}).status_code==409


def test_text_only_and_invalid_reference(tmp_path):
    app=create_app(tmp_path/'home');store=app.state.store
    p=store.register(name='文字镜头')
    s=Shot(description='雨滴落在窗户上。',scene='室内 夜')
    plan=compile_shot_prompt(p,[s],store)
    assert plan['mode']=='text' and plan['references']==[]
    assert '雨滴落在窗户上' in plan['prompt']
    from fastapi import HTTPException
    import pytest
    s.description='@[不存在](asset:missing)'
    with pytest.raises(HTTPException) as error:compile_shot_prompt(p,[s],store)
    assert error.value.status_code==422
