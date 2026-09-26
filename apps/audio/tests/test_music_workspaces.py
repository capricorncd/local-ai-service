import asyncio
from fastapi.testclient import TestClient
from server.app import create_app
from server.core import Manager, connect
from server.models import MusicRequest


def test_empty_workspaces_persist_and_validate(tmp_path):
    with TestClient(create_app(tmp_path, token='secret')) as client:
        assert client.get('/v1/music/workspaces').status_code == 401
        client.headers['Authorization'] = 'Bearer secret'
        assert client.post('/v1/music/workspaces', json={'name': '  BGM  '}).status_code == 201
        assert client.get('/v1/music/workspaces').json() == ['BGM']
        assert client.post('/v1/music/workspaces', json={'name': 'BGM'}).status_code == 409
        assert client.post('/v1/music/workspaces', json={'name': '   '}).status_code == 422
        assert client.post('/v1/music/workspaces', json={'name': 'x' * 61}).status_code == 422
    assert Manager(tmp_path).music_workspaces() == ['BGM']


def test_generation_assigns_every_song_and_preserves_edits(tmp_path, monkeypatch):
    manager = Manager(tmp_path)
    monkeypatch.setattr(manager, 'require', lambda name: None)
    request = MusicRequest(workspace='BGM', title='Test', count=2).model_dump()
    job = asyncio.run(manager.submit('music', request))
    assert [m['group'] for m in job['song_metadata'].values()] == ['BGM', 'BGM']
    manager.edit_song(job['id'], 0, 'Renamed', 'New group')
    manager.update(job['id'], 'succeeded', {'files': [{'title': 'Old'}, {'title': 'Old 2'}]})
    restored = Manager(tmp_path)
    song = restored.job(job['id'])
    assert song['song_metadata']['0'] == {'title': 'Renamed', 'group': 'New group'}
    assert song['song_metadata']['1']['group'] == 'BGM'
    assert set(restored.music_workspaces()) == {'BGM', 'New group'}
    plain = asyncio.run(manager.submit('music', MusicRequest(count=1).model_dump()))
    assert not plain['song_metadata']
    # Existing group metadata is imported without modifying its songs.
    with connect(manager.db_path) as db:
        db.execute('INSERT INTO music_metadata VALUES (?,?,?,?)', (plain['id'], 0, 'Legacy song', 'Legacy group'))
    assert 'Legacy group' in Manager(tmp_path).music_workspaces()
