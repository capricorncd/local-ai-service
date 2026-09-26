import json
from fastapi.testclient import TestClient
from server.app import create_app
from server.core import Manager, connect


def test_playback_is_per_track_persistent_and_idempotent(tmp_path):
    with TestClient(create_app(tmp_path, token='secret')) as client:
        manager = client.app.state.manager
        output = tmp_path / 'track.wav'
        output.write_bytes(b'RIFF-audio')
        with connect(manager.db_path) as db:
            db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?,NULL)',
                       ('song', 'music', 'succeeded', 0, 0, '{}', json.dumps({'files': [{'path':str(output)}, {'path':str(output)}]})))
            db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,NULL,NULL)', ('pending', 'music', 'queued', 0, 0, '{}'))
        url = '/v1/music/jobs/song/songs/0/played'
        assert client.post(url).status_code == 401
        client.headers['Authorization'] = 'Bearer secret'
        assert client.get('/v1/jobs/song').json()['played_indices'] == []
        # Reading/downloading files is not a playback signal.
        assert client.get('/v1/jobs/song/files/0').status_code == 200
        assert manager.job('song')['played_indices'] == []
        assert client.post(url).json()['played_indices'] == [0]
        assert client.post(url).json()['played_indices'] == [0]
        assert client.post('/v1/music/jobs/song/songs/2/played').status_code == 404
        assert client.post('/v1/music/jobs/song/songs/-1/played').status_code == 404
        assert client.post('/v1/music/jobs/pending/songs/0/played').status_code == 404
        manager.edit_song('song', 0, 'Renamed', 'Workspace')
        with connect(manager.db_path) as db:
            assert db.execute('SELECT COUNT(*) FROM music_playbacks').fetchone()[0] == 1
    assert Manager(tmp_path).job('song')['played_indices'] == [0]
