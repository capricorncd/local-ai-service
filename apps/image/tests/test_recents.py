import sys
import sqlite3
from pathlib import Path
from fastapi.testclient import TestClient

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'server'))
from domain import Project
from recents import RecentStore
from app import create_app

def project(index=0):
    source='data:image/png;base64,aGVsbG8='
    return Project(format='local-ai-image',version=1,name='工程',width=1024,height=1024,
        layers=[dict(id='layer',name='图层',source=source,width=1,height=1,x=-12,y=10,scale=2,opacity=.5,visible=False,locked=True,reference=True)],
        active='layer',mask=source,prompt=f'操作 {index}',negative='negative',mode='brush',steps=12,cfg=3.5,seed=42)

def test_bounded_history_roundtrip_and_dedup(tmp_path):
    path=tmp_path/'history.sqlite3'
    store=RecentStore(path)
    ids=[store.save(project(i))['id'] for i in range(35)]
    records=store.list()
    assert len(records)==30
    assert [r['id'] for r in records]==ids[5:][::-1]
    assert store.get(ids[0]) is None
    assert store.get(ids[-1])==project(34).model_dump()
    assert store.save(project(34))['id']==ids[-1]
    assert len(store.list())==30
    # Reopening the store after restart retains images and all editor values.
    assert RecentStore(path).get(ids[10])==project(10).model_dump()
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT COUNT(*) FROM recent_assets').fetchone()[0]==1
        assert db.execute('SELECT COUNT(*) FROM recent_links').fetchone()[0]==30
    empty=project(40).model_copy(update={'layers':[],'active':None,'mask':None})
    for i in range(30):
        store.save(empty.model_copy(update={'prompt':str(i)}))
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT COUNT(*) FROM recent_assets').fetchone()[0]==0

def test_history_api_auth_and_restore(tmp_path):
    app=create_app(tmp_path)
    with TestClient(app) as client:
        assert client.get('/v1/recents').status_code==401
        client.headers['Authorization']='Bearer '+(tmp_path/'api-token').read_text()
        data=project().model_dump()
        saved=client.post('/v1/recents',json=data)
        assert saved.status_code==200
        id=saved.json()['id']
        assert client.get('/v1/recents/'+id).json()==data
        assert 'content' not in client.get('/v1/recents').json()[0]
        assert client.get('/v1/recents/not-found').status_code==404
        assert client.post('/v1/recents',json={**data,'version':20}).status_code==422
