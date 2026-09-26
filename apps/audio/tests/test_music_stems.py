import asyncio
import json
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from server.app import create_app
from server.core import Manager, connect

def test_song_separation_contract(tmp_path,monkeypatch):
    monkeypatch.setenv('LOCAL_AI_DESKTOP','1')
    app=create_app(tmp_path,token='public')
    with TestClient(app) as client:
        manager=app.state.manager
        audio=tmp_path/'original.wav';audio.write_bytes(b'RIFF')
        with connect(manager.db_path) as db:
            db.execute('insert into jobs values (?,?,?,?,?,?,?,?)',('source','music','succeeded',0,0,'{}',json.dumps({'files':[{'path':str(audio),'title':'Original'}]}),None))
        manager.edit_song('source',0,'My Song','Group A')
        submit=AsyncMock(return_value={'id':'split','status':'queued'})
        monkeypatch.setattr(manager,'submit',submit)
        url='/internal/music/separate'
        assert client.post(url,json={'job_id':'source'},headers={'Authorization':'Bearer public'}).status_code==403
        client.headers['X-Desktop-Key']=(tmp_path/'desktop-token').read_text()
        assert client.post(url,json={'job_id':'source'}).status_code==202
        request=submit.call_args.args[1]
        assert request['operation']=='separate' and request['count']==2
        assert request['source_title']=='My Song' and request['source_group']=='Group A'
        assert request['song_titles']==['My Song · 人声','My Song · 伴奏']
        assert request['input_path']==str(audio)
        assert client.post(url,json={'job_id':'source','audio_index':2}).status_code==404
        assert client.post(url,json={'job_id':'source','audio_index':-1}).status_code==422
        audio.unlink()
        assert client.post(url,json={'job_id':'source'}).status_code==404

def test_separation_queue_dedup_and_metadata(tmp_path):
    manager=Manager(tmp_path)
    manager.states['music']={'status':'ready'}
    params={'operation':'separate','source_job_id':'source','source_audio_index':0,'source_title':'A','input_path':'source.wav','count':2,'song_titles':['A vocals','A backing']}
    first=asyncio.run(manager.submit('music',params.copy()))
    second=asyncio.run(manager.submit('music',params.copy()))
    assert first['id']==second['id'] and manager.queue.qsize()==1
    _,_,queued,_=manager.queue.get_nowait()
    assert queued['song_titles']==params['song_titles'] and 'steps' not in queued
    manager.update(first['id'],'succeeded',{'files':[{'tag':'vocals','path':'v.wav'},{'tag':'instrumental','path':'i.wav'}]})
    manager.edit_song(first['id'],1,'Backing','My Group')
    saved=manager.job(first['id'])
    assert saved['result']['files'][1]['tag']=='instrumental'
    assert saved['song_metadata']['1']=={'title':'Backing','group':'My Group'}


def test_uploaded_music_separation(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCAL_AI_DESKTOP','1')
    with TestClient(create_app(tmp_path,token='public')) as client:
        client.headers['Authorization']='Bearer public'
        uploaded=client.post('/v1/uploads',files={'file':('song.mp4',b'video')}).json()['upload_id']
        endpoint='/internal/music/separate-upload'
        assert client.post(endpoint,json={'upload_id':uploaded}).status_code==403
        client.headers['X-Desktop-Key']=(tmp_path/'desktop-token').read_text()
        submit=AsyncMock(return_value={'id':'split','status':'queued'})
        monkeypatch.setattr(client.app.state.manager,'submit',submit)
        assert client.post(endpoint,json={'upload_id':uploaded,'title':'Song'}).status_code==202
        service,request=submit.call_args.args
        assert service=='music' and request['operation']=='separate'
        assert request['song_titles']==['Song · 人声','Song · 伴奏']
        assert request['source_job_id']=='upload:'+uploaded
        assert request['input_path']==str((tmp_path/'uploads'/uploaded).resolve())
        assert client.post(endpoint,json={'upload_id':'../secret'}).status_code==404
        assert client.post(endpoint,json={'upload_id':'missing.wav'}).status_code==404
