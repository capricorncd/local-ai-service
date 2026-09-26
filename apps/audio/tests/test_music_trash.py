import asyncio
import json
import uuid
from pathlib import Path
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from server.app import create_app
from server.core import Manager, connect
from server import recycle


def create_job(manager, status='succeeded'):
    job_id = uuid.uuid4().hex
    folder = Path(manager.active.music.output_dir) / job_id
    folder.mkdir(parents=True)
    files = []
    for index in range(2):
        path = folder / f'song-{index}.wav'
        path.write_bytes(b'audio')
        files.append({'path':str(path),'url':f'/v1/jobs/{job_id}/files/{index}'})
    score = folder / 'song.abc'
    score.write_text('X:1\nK:C\nC|', 'utf-8')
    (folder / 'worker.log').write_text('test', 'utf-8')
    result = {'files':files,'scores':[{'path':str(score),'audio_index':0,'mode':'full'}]}
    with connect(manager.db_path) as db:
        db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?)', (job_id,'music',status,0,0,'{}',json.dumps(result),None))
    return job_id, folder


def test_delete_entire_directory_and_hide_job(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCAL_AI_DESKTOP','1')
    with TestClient(create_app(tmp_path / 'app',token='secret')) as client:
        manager = client.app.state.manager
        job_id, folder = create_job(manager)
        unrelated_id, unrelated = create_job(manager)
        def move(directory):
            directory.rename(tmp_path / 'mock-trash')
        trash = Mock(side_effect=move)
        monkeypatch.setattr(recycle,'recycle_directory',trash)
        endpoint = f'/internal/music/jobs/{job_id}'
        client.headers['Authorization']='Bearer secret'
        assert client.delete(endpoint).status_code == 403
        client.headers['X-Desktop-Key']=(tmp_path / 'app/desktop-token').read_text()
        assert client.delete(endpoint).json()['trashed'] is True
        trash.assert_called_once_with(folder)
        assert sorted(p.name for p in (tmp_path / 'mock-trash').iterdir()) == ['song-0.wav','song-1.wav','song.abc','worker.log']
        assert unrelated.is_dir()
        assert [job['id'] for job in client.get('/v1/jobs').json()] == [unrelated_id]
        assert client.get(f'/v1/jobs/{job_id}').status_code == 404
        assert client.get(f'/v1/jobs/{job_id}/files/1').status_code == 404
        assert client.get(f'/v1/jobs/{job_id}/scores/0').status_code == 404
        assert client.delete(endpoint).status_code == 404
        assert all(j['id'] != job_id for j in Manager(tmp_path / 'app').jobs())


@pytest.mark.parametrize('scenario', ['running','dependency','outside','failure'])
def test_refuse_unsafe_or_failed_delete(tmp_path, monkeypatch, scenario):
    manager = Manager(tmp_path / 'app')
    job_id, folder = create_job(manager, 'running' if scenario == 'running' else 'succeeded')
    if scenario == 'dependency':
        with connect(manager.db_path) as db:
            db.execute('INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?)', ('dependent','music','queued',0,0,json.dumps({'reference_audio_path':str(folder/'song-0.wav')}),None,None))
    if scenario == 'outside':
        job = manager.job(job_id)
        job['result']['files'][0]['path'] = str(tmp_path / 'outside.wav')
        manager.update(job_id,'succeeded',job['result'])
    trash = Mock(side_effect=OSError('Recycle Bin unavailable'))
    monkeypatch.setattr(recycle,'recycle_directory',trash)
    with pytest.raises(HTTPException) as error:
        asyncio.run(manager.trash_music_job(job_id))
    assert error.value.status_code == 409
    assert folder.is_dir() and manager.job(job_id)
    assert trash.call_count == (1 if scenario == 'failure' else 0)
