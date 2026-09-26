import json
from fastapi.testclient import TestClient
from server.app import create_app
from server.core import Manager, connect


def test_annotations_validate_and_persist_per_track(tmp_path):
    with TestClient(create_app(tmp_path, token='secret')) as client:
        manager = client.app.state.manager
        with connect(manager.db_path) as db:
            for job_id, service, status in [('song', 'music', 'succeeded'), ('pending', 'music', 'queued'), ('speech', 'tts', 'succeeded')]:
                db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?,NULL)',
                           (job_id, service, status, 0, 0, '{}', json.dumps({'files': [{}, {}]})))
        url = '/v1/music/jobs/song/songs/0/annotation'
        value = {'rating': 4, 'favorite': True}
        assert client.put(url, json=value).status_code == 401
        client.headers['Authorization'] = 'Bearer secret'
        assert manager.job('song')['song_annotations'] == {}
        assert client.put(url, json=value).json() == value
        for rating in [-1, 6, 2.5, True, '3']:
            assert client.put(url, json={**value, 'rating': rating}).status_code == 422
        assert client.put(url, json={**value, 'favorite': 'true'}).status_code == 422
        for job_id, index in [('song', -1), ('song', 2), ('pending', 0), ('speech', 0), ('missing', 0)]:
            assert client.put(f'/v1/music/jobs/{job_id}/songs/{index}/annotation', json=value).status_code == 404
        second = {'rating': 5, 'favorite': False}
        assert client.put(url.replace('/0/', '/1/'), json=second).json() == second
        cleared = {'rating': 0, 'favorite': False}
        assert client.put(url, json=cleared).json() == cleared
        manager.edit_song('song', 1, 'Renamed', 'Workspace')
        manager.mark_music_played('song', 1)
        expected = {'0': cleared, '1': second}
        assert client.get('/v1/jobs/song').json()['song_annotations'] == expected
    restored = Manager(tmp_path).job('song')
    assert restored['song_annotations'] == expected
    assert restored['song_metadata']['1']['group'] == 'Workspace'
    assert restored['played_indices'] == [1]
