import json
from fastapi.testclient import TestClient
from server.app import create_app
from server.core import connect


def test_scoped_playback_supports_ranges(tmp_path):
    with TestClient(create_app(tmp_path,token='secret')) as client:
        file=tmp_path/'audio.wav';file.write_bytes(b'RIFF'+bytes(range(100)))
        with connect(client.app.state.manager.db_path) as db:
            db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?,NULL)',('song','music','succeeded',0,0,'{}',json.dumps({'files':[{'path':str(file)}]})))
        source={'source':'/v1/jobs/song/files/0'}
        assert client.post('/v1/playback',json=source).status_code==401
        auth={'Authorization':'Bearer secret'}
        result=client.post('/v1/playback',json=source,headers=auth)
        assert result.status_code==200
        url=result.json()['url']
        response=client.get(url,headers={'Range':'bytes=0-3'})
        assert response.status_code==206 and response.content==b'RIFF'
        assert client.get('/v1/playback/unknown').status_code==404
        assert client.post('/v1/playback',json={'source':str(file)},headers=auth).status_code==422
        assert client.post('/v1/playback',json={'source':'/v1/jobs/song/files/1'},headers=auth).status_code==404
        file.unlink()
        assert client.get(url).status_code==404
