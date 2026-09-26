from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from server.app import create_app


def test_public_modes_and_multipart(tmp_path, monkeypatch):
    with TestClient(create_app(tmp_path, token='secret')) as client:
        manager=client.app.state.manager
        monkeypatch.setattr(manager,'require',lambda name:None)
        submit=AsyncMock(side_effect=lambda service,params:{'id':service,'status':'queued'})
        monkeypatch.setattr(manager,'submit',submit)
        assert client.post('/v1/separate',json={'upload_id':'x'}).status_code==401
        client.headers['Authorization']='Bearer secret'
        upload=client.post('/v1/uploads',files={'file':('song.wav',b'RIFF')}).json()['upload_id']
        for mode,expected in [('speakers',['separation']),('music',['music']),('both',['separation','music'])]:
            submit.reset_mock()
            response=client.post('/v1/separate?wait=false',json={'upload_id':upload,'mode':mode})
            assert response.status_code==202,response.text
            assert [call.args[0] for call in submit.call_args_list]==expected
            if mode=='both':assert len(response.json()['jobs'])==2
        submit.reset_mock()
        assert client.post('/v1/separate?wait=false',json={'upload_id':upload}).status_code==202
        assert submit.call_args.args[0]=='separation'
        assert client.post('/v1/separate',json={'upload_id':upload,'mode':'bad'}).status_code==422
        response=client.post('/v1/separate/file?wait=false',data={'mode':'music','title':'Song'},files={'file':('song.mp4',b'video')})
        assert response.status_code==202
        assert submit.call_args.args[1]['song_titles']==['Song · 人声','Song · 伴奏']
        completed={service:{'id':service,'status':'succeeded','result':{'files':[{'tag':service+'1'},{'tag':service+'2'}]}} for service in ['separation','music']}
        monkeypatch.setattr(manager,'submit',AsyncMock(side_effect=lambda service,params:completed[service]))
        monkeypatch.setattr(manager,'job',lambda job_id:completed[job_id])
        response=client.post('/v1/separate',json={'upload_id':upload,'mode':'both'})
        assert response.status_code==200
        assert len(response.json()['files'])==4
        assert len(response.json()['jobs'])==2
