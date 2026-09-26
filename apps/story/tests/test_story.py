import io
import json
import sys
import wave
import zipfile
from pathlib import Path
import pytest
import httpx
from PIL import Image
from fastapi.testclient import TestClient

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
from app import create_app
from domain import Project, Chapter, Episode, Shot, Asset, import_script, parse_agent_shots
from storage import Store
from timeline import export_timeline, bundle
import image_metadata


@pytest.fixture
def service(tmp_path):
    home=tmp_path/'service';app=create_app(home)
    with TestClient(app) as client:
        client.headers['Authorization']='Bearer '+(home/'api-token').read_text()
        p=client.post('/v1/projects/open',json={'name':'雨夜来客','directory':str(tmp_path/'project')}).json()
        yield client,p,app.state.store


def test_agent_crud_history_conflict_and_rollback(service):
    c,p,store=service;b='/v1/projects/'+p['id']
    r=c.post(b+'/chapters',json={'revision':0,'data':{'title':'第二季'},'reason':'新增第二季','actor':'Codex'})
    assert r.status_code==200,r.text
    chapter=r.json()['ids'][0]
    assert c.get(b+'/history').json()[0]['reason']=='Codex · 新增第二季'
    assert c.post(b+'/chapters',json={'revision':0,'data':{'title':'冲突'}}).status_code==409
    r=c.post(b+f'/chapters/{chapter}/episodes',json={'revision':1,'data':{'title':'特别篇','kind':'special','script':'陈墨：你好。'}})
    ep=r.json()['ids'][0]
    assert c.get(b+'/content',params={'chapter_id':chapter}).json()['chapters'][0]['episodes'][0]['script']=='陈墨：你好。'
    r=c.post(b+f'/episodes/{ep}/shots',json={'revision':2,'data':{'title':'推门','dialogue':'你好。','duration':2}})
    shot=r.json()['ids'][0]
    r=c.patch(b+'/shots/'+shot,json={'revision':3,'data':{'dialogue':'等等。'},'reason':'修订对白'})
    assert r.json()['project']['chapters'][1]['episodes'][0]['shots'][0]['dialogue']=='等等。'
    assert c.get(b+'/history/00000003').json()['project']['chapters'][1]['episodes'][0]['shots'][0]['dialogue']=='你好。'
    r=c.post(b+'/transactions',json={'revision':4,'reason':'原子测试','operations':[{'entity':'chapter','action':'create','data':{'title':'不应写入'}},{'entity':'shot','action':'update','id':'missing','data':{}}]})
    assert r.status_code==404
    assert len(c.get(b).json()['chapters'])==2
    assert c.get(b).json()['revision']==4
    assert c.patch(b+'/shots/'+shot,json={'revision':4,'data':{'duration':0}}).status_code==422
    r=c.post(b+'/history/00000003/restore',json={'revision':4})
    assert r.status_code==200 and r.json()['revision']==5
    assert c.get(b+'/history/00000004').status_code==200


def test_import_text_assets_auth_and_paths(service,tmp_path):
    c,p,store=service;b='/v1/projects/'+p['id']
    text='# 第一季\n## 第1话 夜雨\n△ 推门。\n陈墨（低声）：有人吗？\n## 特别篇\n【音效】雨声。'
    r=c.post('/v1/import-script',files={'file':('故事.md',text.encode('utf-8-sig'))})
    chapters=r.json()['chapters'];assert len(chapters)==1
    assert len(chapters[0]['episodes'])==2 and chapters[0]['episodes'][1]['kind']=='special'
    assert '陈墨（低声）：有人吗？' in chapters[0]['episodes'][0]['script']
    im=io.BytesIO();Image.new('RGBA',(32,32),(50,60,70,0)).save(im,format='PNG')
    r=c.post(b+'/media',files={'file':('test.png',im.getvalue())});rel=r.json()['path']
    assert image_metadata.image_digest(c.get(b+'/'+rel).content)==image_metadata.image_digest(im.getvalue())
    assert r.json()['metadata_status']=='unavailable'
    with pytest.raises(Exception):store.media(p['id'],'media/../../secrets')
    r=c.post('/v1/projects/open',json={'directory':str(tmp_path/'project'),'name':'覆盖'})
    assert r.status_code==409
    c.headers.pop('Authorization');assert c.get(b).status_code==401


def test_timeline_media_audio_frames_and_disabled(service):
    c,raw,store=service;p=Project.model_validate(raw)
    path=store.root(p.id)/'media'/('a'*32+'.png');Image.new('RGBA',(32,32),(1,2,3,4)).save(path)
    meta={'schema_version':1,'asset_name':'陈墨','asset_type':'character','generation_prompt':None,'generation_prompt_status':'unavailable','generation_prompt_source':'Imported with no reliable original record','generation_mode':'unknown','reference_images':[],'setting_description':'青年，黑色短发，灰色外套。','consistency_constraints':['外套保持灰色']}
    before=image_metadata.image_digest(path.read_bytes());image_metadata.write(path,meta,store.root(p.id)/'backups')
    assert image_metadata.image_digest(path.read_bytes())==before
    a=Asset(name='陈墨',image='media/'+path.name);p.assets=[a]
    ep=p.chapters[0].episodes[0]
    ep.shots=[Shot(title='一帧',duration=1/24,description='抬眼',asset_ids=[a.id],image=a.image),Shot(title='再一帧',duration=1/24),Shot(title='禁用',disabled=True)]
    result,board,files,warnings=export_timeline(p,ep,store)
    clips=result['tracks'][0]['clips'];assert [(x['start_ms'],x['duration_ms']) for x in clips]==[(0,42),(42,41)]
    assert not board['shots'][2]['clip_ids']
    assert '青年，黑色短发' in clips[0]['prompt']
    assert result['settings']['width']==1376 and result['settings']['append_prompt']=='non_diegetic_music:\nn/a.'
    data=bundle(result,board,files,warnings)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        assert 'media/images/'+path.name in z.namelist()
        assert z.read('media/images/'+path.name)==path.read_bytes()
    wav=store.root(p.id)/'media'/('b'*32+'.wav')
    with wave.open(str(wav),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(b'\0'*48000)
    ep.shots=[Shot(title='对白',duration=2,speaker='陈墨',dialogue='你好。等等！',audio='media/'+wav.name,audio_text='你好。等等！',audio_duration=1)]
    result,_,files,_=export_timeline(p,ep,store)
    assert result['tracks'][-1]['type']=='audio'
    assert 'media/audios/'+wav.name in files
    subtitles=result['tracks'][1]['clips'];assert len(subtitles)==2
    assert all(s['character_media_id'] for s in subtitles)


def test_agent_rejects_unknown_assets_and_no_invented_files():
    with pytest.raises(ValueError):parse_agent_shots('{"shots":[{"asset_ids":["fake"]}]}',[])
    shots=parse_agent_shots('```json\n{"shots":[{"description":"开门","image":"fake.png","images":["reference.png"],"hidden_images":["fake.png"],"audio":"fake.wav"}]}\n```',[])
    assert shots[0].image==shots[0].audio==''
    assert shots[0].images==shots[0].hidden_images==[]


def test_audio_bridge_and_stale_apply(service,monkeypatch):
    c,p,store=service;b='/v1/projects/'+p['id'];p['assets']=[Asset(name='陈墨',voice_preset='dylan').model_dump()]
    shot=Shot(speaker='陈墨',dialogue='你终于来了。',emotion='低声',duration=3)
    p['chapters'][0]['episodes'][0]['shots']=[shot.model_dump()]
    p=c.put(b,json=p).json()
    c.put('/v1/settings',json={'audio_token':'test','image_token':'test'})
    wav=io.BytesIO()
    with wave.open(wav,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000);w.writeframes(b'\0'*48000)
    calls=[]
    def handle(req):
        calls.append(req)
        if req.url.path=='/v1/tts/generate':
            body=json.loads(req.content);assert body['text']=='你终于来了。';assert body['speaker']=='dylan';assert body['instruct']=='低声'
            return httpx.Response(202,json={'id':'tts-1','status':'queued'})
        if req.url.path.endswith('/files/0'):return httpx.Response(200,content=wav.getvalue())
        if req.url.path.endswith('/tts-1'):return httpx.Response(200,json={'status':'succeeded','result':{'files':[{}]}})
        raise AssertionError(str(req.url))
    Original=httpx.Client
    monkeypatch.setattr('app.httpx.Client',lambda **kwargs:Original(transport=httpx.MockTransport(handle),**kwargs))
    job=c.post(b+'/speech',json={'shot_id':shot.id,'revision':1}).json()
    done=c.get(b+'/jobs/'+job['id']);assert done.status_code==200,done.text
    assert done.json()['duration']==1 and done.json()['status']=='completed'
    applied=c.post(b+'/jobs/'+job['id']+'/apply',json={'revision':1});assert applied.status_code==200,applied.text
    assert applied.json()['chapters'][0]['episodes'][0]['shots'][0]['audio_text']=='你终于来了。'
    c.patch(b+'/shots/'+shot.id,json={'revision':2,'data':{'dialogue':'换台词。'}})
    assert c.post(b+'/jobs/'+job['id']+'/apply',json={'revision':3}).status_code==409
    assert c.get(b+'/history/00000001').status_code==200


def test_image_bridge_exact_prompt_metadata_and_history(service,monkeypatch):
    c,p,store=service;b='/v1/projects/'+p['id']
    a=Asset(name='纸偶',kind='prop',description='白色折纸人偶，蓝色眼睛。',constraints='单只人偶')
    p['assets']=[a.model_dump()];p=c.put(b,json=p).json()
    c.put('/v1/settings',json={'image_token':'test'})
    im=io.BytesIO();Image.new('RGBA',(32,32),(12,34,56,78)).save(im,format='PNG')
    submitted={}
    def handle(req):
        if req.method=='POST' and req.url.path=='/v1/jobs':
            submitted.update(json.loads(req.content));return httpx.Response(202,json={'id':'image-1','status':'queued'})
        if req.url.path.endswith('/image'):return httpx.Response(200,content=im.getvalue())
        return httpx.Response(200,json={'status':'completed','progress':100})
    Original=httpx.Client
    monkeypatch.setattr('app.httpx.Client',lambda **kwargs:Original(transport=httpx.MockTransport(handle),**kwargs))
    r=c.post(b+'/generate',json={'kind':'asset','target_id':a.id,'prompt':'正面全身'})
    assert r.status_code==200,r.text
    jid=r.json()['id'];done=c.get(b+'/jobs/'+jid);assert done.status_code==200,done.text
    path=store.media(p['id'],done.json()['path']);record=image_metadata.read(path)
    assert record['generation_prompt']==submitted['prompt']
    assert record['setting_description'].startswith('白色折纸人偶')
    assert image_metadata.image_digest(path.read_bytes())==image_metadata.image_digest(im.getvalue())
    assert c.post(b+'/jobs/'+jid+'/apply',json={'revision':1}).status_code==200
    assert c.get(b+'/history/00000001').json()['project']['assets'][0]['image']==''


def test_agent_receives_skill_and_selection_only(service,monkeypatch):
    c,p,_=service;c.put('/v1/settings',json={'model':'test'})
    calls=[]
    def handle(req):
        body=json.loads(req.content);calls.append(body)
        return httpx.Response(200,json={'message':{'content':'△ 陈墨攥紧手电筒。'}})
    Original=httpx.Client
    monkeypatch.setattr('integrations.httpx.Client',lambda **kwargs:Original(transport=httpx.MockTransport(handle),**kwargs))
    r=c.post('/v1/projects/'+p['id']+'/agent',json={'mode':'rewrite','content':'他很害怕。','instruction':'改为可见动作'})
    assert r.json()['text']=='△ 陈墨攥紧手电筒。'
    assert 'AI 漫剧文字分镜' in calls[0]['messages'][0]['content']
    assert json.loads(calls[0]['messages'][1]['content'])['待处理正文']=='他很害怕。'
    assert c.get('/v1/projects/'+p['id']).json()['revision']==0


def test_database_optional_directory_and_restart(tmp_path):
    store=Store(tmp_path/'home')
    p=store.register(name='数据库正文')
    root=store.root(p.id)
    assert root.parent == (tmp_path/'home/projects').resolve()
    assert not (root/'story.json').exists()
    p.chapters[0].episodes[0].script='完整正文与对白。'
    saved=store.save(p.id,p)
    restarted=Store(tmp_path/'home')
    assert restarted.load(p.id).chapters[0].episodes[0].script=='完整正文与对白。'
    assert restarted.history(p.id,'00000000')['project']['revision']==0
    with pytest.raises(Exception): restarted.save(p.id,p)
    assert restarted.load(p.id).revision==1
    other=store.register(name='自定义',default_directory=str(tmp_path/'custom'))
    assert store.root(other.id).parent == (tmp_path/'custom').resolve()
    assert store.register(str(root)).id==p.id


def test_legacy_database_migration(tmp_path):
    home=tmp_path/'home';home.mkdir()
    root=tmp_path/'legacy';(root/'history').mkdir(parents=True)
    old=Project(name='旧工程',chapters=[Chapter(episodes=[Episode(script='旧正文')])])
    current=old.model_copy(deep=True);current.revision=1
    current.chapters[0].episodes[0].script='最新正文'
    (root/'story.json').write_text(current.model_dump_json(),'utf-8')
    (root/'history/00000000.json').write_text(json.dumps({'reason':'旧历史','project':old.model_dump()},ensure_ascii=False),'utf-8')
    (home/'projects.json').write_text(json.dumps({old.id:str(root)}),'utf-8')
    store=Store(home)
    assert store.load(old.id).chapters[0].episodes[0].script=='最新正文'
    assert store.history(old.id,'00000000')['project']['chapters'][0]['episodes'][0]['script']=='旧正文'
    current.chapters[0].episodes[0].script='入库后修改'
    store.save(old.id,current)
    assert Store(home).load(old.id).chapters[0].episodes[0].script=='入库后修改'
    assert Project.model_validate_json((root/'story.json').read_text('utf-8')).revision==1


def test_create_without_directory_api(service,tmp_path):
    c,_,store=service
    response=c.post('/v1/projects/open',json={'name':'无需目录'})
    assert response.status_code==200,response.text
    assert not (store.root(response.json()['id'])/'story.json').exists()
    assert c.post('/v1/projects/open',json={}).status_code==422
    assert c.put('/v1/settings',json={'project_directory':'relative'}).status_code==422
    c.put('/v1/settings',json={'project_directory':str(tmp_path/'configured')})
    p=c.post('/v1/projects/open',json={'name':'配置目录'}).json()
    assert store.root(p['id']).parent==(tmp_path/'configured').resolve()


def test_unnamed_unique_name_and_directory_rename(tmp_path):
    store=Store(tmp_path/'home')
    p=store.register(name='')
    assert p.name==p.id and store.root(p.id).name==p.id
    before=store.root(p.id)
    marker=before/'media'/'keep.txt';marker.write_text('保留素材','utf-8')
    p.name='失踪七日'
    p=store.save(p.id,p)
    assert store.root(p.id).name=='失踪七日'
    assert (store.root(p.id)/'media/keep.txt').read_text('utf-8')=='保留素材'
    assert not before.exists()
    with pytest.raises(Exception):store.register(name='失踪七日')
    other=store.register(name='其他')
    other.name='失踪七日'
    with pytest.raises(Exception):store.save(other.id,other)
    assert store.load(other.id).name=='其他'
    target=store.root(p.id).parent/'已存在';target.mkdir()
    p.name='已存在'
    with pytest.raises(Exception):store.save(p.id,p)
    assert store.load(p.id).name=='失踪七日'
    assert len(store.versions(p.id))==1


def test_large_project_save_does_not_read_from_second_connection(tmp_path):
    import sqlite3
    class SmallCacheStore(Store):
        def connect(self):
            db=sqlite3.connect(self.database,timeout=0.1)
            db.execute('PRAGMA cache_size=10')
            return db
    store=SmallCacheStore(tmp_path/'large')
    with store.connect() as db: db.execute('PRAGMA journal_mode=DELETE')
    p=store.register(name='大工程')
    p.chapters[0].episodes[0].script='剧本正文。'*500000
    p=store.save(p.id,p)
    p.chapters[0].episodes[0].script+='本次修改'
    p=store.save(p.id,p)
    assert store.load(p.id).revision==2
    assert store.load(p.id).chapters[0].episodes[0].script.endswith('本次修改')
    assert store.history(p.id,'00000001')['project']['chapters'][0]['episodes'][0]['script']=='剧本正文。'*500000


def test_unexpected_save_error_has_cors_and_request_log(service,monkeypatch,caplog):
    import sqlite3
    c,p,store=service
    def fail(*args,**kwargs):raise sqlite3.OperationalError('database is locked')
    monkeypatch.setattr(store,'save',fail)
    path='/v1/projects/'+p['id']
    r=c.put(path,json=p,headers={'Origin':'http://tauri.localhost'})
    assert r.status_code==500
    assert r.headers['access-control-allow-origin']=='http://tauri.localhost'
    assert path in r.json()['detail']
    assert 'PUT '+path in caplog.text and 'database is locked' in caplog.text
    assert (store.home/'api-token').read_text() not in caplog.text


def test_unchanged_save_does_not_create_history(service):
    client,p,store=service
    path='/v1/projects/'+p['id']
    p['updated']='ignored client timestamp'
    result=client.put(path,json=p)
    assert result.status_code==200
    assert result.json()['revision']==0
    assert result.json()['updated']!=p['updated']
    assert client.get(path+'/history').json()==[]
    p=result.json();p['chapters'][0]['episodes'][0]['script']='真实修改'
    changed=client.put(path,json=p).json()
    assert changed['revision']==1
    assert client.put(path,json=changed).json()['revision']==1
    assert len(store.versions(p['id']))==1

def test_storyboard_max_edge_setting_and_generation(service, monkeypatch):
    from domain import Settings, storyboard_image_size
    c,p,_=service;b='/v1/projects/'+p['id']
    assert c.get('/v1/settings').json()['storyboard_max_edge']==1024
    assert c.put('/v1/settings',json={'storyboard_max_edge':1001}).status_code==422
    assert c.put('/v1/settings',json={'storyboard_max_edge':0}).status_code==422
    shot=Shot(description='窗边的人物');episode=Episode(shots=[shot]);asset=Asset(name='角色',description='蓝色外套')
    p['chapters']=[Chapter(episodes=[episode]).model_dump()];p['assets']=[asset.model_dump()]
    assert c.put(b,json=p).status_code==200
    submitted=[]
    def handle(req):
        submitted.append(json.loads(req.content));return httpx.Response(202,json={'id':'test','status':'queued'})
    Original=httpx.Client
    monkeypatch.setattr('app.httpx.Client',lambda **kwargs:Original(transport=httpx.MockTransport(handle),**kwargs))
    for request in [{'kind':'shot','target_id':shot.id},{'kind':'board','target_id':episode.id,'shot_ids':[shot.id]},{'kind':'asset','target_id':asset.id}]:
        response=c.post(b+'/generate',json=request);assert response.status_code==200,response.text
    assert [(r['width'],r['height']) for r in submitted]==[(1024,576),(1024,576),(1376,768)]
    assert c.put('/v1/settings',json={'storyboard_max_edge':768}).status_code==200
    assert c.get('/v1/settings').json()['storyboard_max_edge']==768
    assert c.post(b+'/generate',json={'kind':'shot','target_id':shot.id}).status_code==200
    assert (submitted[-1]['width'],submitted[-1]['height'])==(768,416)
    assert c.get(b).json()['width']==1376
    assert storyboard_image_size(768,1376,1024)==(576,1024)
    assert storyboard_image_size(512,512,1024)==(512,512)
    assert storyboard_image_size(2048,256,1024)==(1024,256)
