import asyncio
import contextlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from server.app import create_app
from server.core import Manager


def test_transcribe_endpoint(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCAL_AI_DESKTOP', '1')
    with TestClient(create_app(tmp_path, token='public')) as client:
        manager = client.app.state.manager
        manager.states['music'] = {'status': 'ready'}
        encoder = tmp_path / 'encoder.safetensors'
        encoder.write_bytes(b'test')
        manager.active.music.encoder_path = str(encoder)
        client.headers['Authorization'] = 'Bearer public'
        uploaded = client.post('/v1/uploads', files={'file': ('song.mp3', b'audio')}).json()['upload_id']
        payload = {'upload_id': uploaded, 'title': 'My score', 'workspace': ' Test ', 'mode': 'melody'}
        url = '/internal/music/transcribe'
        assert client.post(url, json=payload).status_code == 403
        client.headers['X-Desktop-Key'] = (tmp_path / 'desktop-token').read_text()
        submit = AsyncMock(return_value={'id': 'score', 'status': 'queued'})
        monkeypatch.setattr(manager, 'submit', submit)
        assert client.post(url, json=payload).status_code == 202
        service, request = submit.call_args.args
        assert service == 'music'
        assert request['operation'] == 'transcribe' and request['count'] == 1
        assert request['generate_score'] and request['mode'] == 'melody'
        assert request['workspace'] == 'Test'
        assert Path(request['reference_audio_path']).read_bytes() == b'audio'
        assert 'lyrics' not in request and 'planner_lora' not in request
        assert client.post(url, json={**payload, 'mode': 'off'}).status_code == 422
        for upload_id in ('missing.wav', '../secret'):
            assert client.post(url, json={**payload, 'upload_id': upload_id}).status_code == 404
        encoder.unlink()
        assert client.post(url, json=payload).status_code == 409


def test_transcribe_worker_does_not_load_generation_model(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'server'))
    import score_worker
    from server.worker import music
    abc = 'X:1\nT:Test\nM:4/4\nL:1/4\nK:C\nC D E F|'
    monkeypatch.setattr(score_worker, 'extract_reference_score', lambda *_: abc)
    result = music({}, {'operation': 'transcribe', 'title': 'Test', 'mode': 'full'}, tmp_path)
    assert result['files'] == [] and result['model'] == 'SheetSage2'
    assert Path(result['scores'][0]['path']).read_text('utf-8') == abc
    assert not list(tmp_path.glob('*.wav'))


@pytest.mark.parametrize('operation,has_score,expected', [
    ('transcribe', True, 'succeeded'), ('transcribe', False, 'failed'), ('generate', True, 'failed')])
def test_score_only_queue_result(tmp_path, monkeypatch, operation, has_score, expected):
    from server import core
    manager = Manager(tmp_path)
    manager.states['music'] = {'status': 'ready'}
    async def subprocess_stub(*args, **kwargs):
        payload = json.loads(Path(args[2]).read_text('utf-8'))
        output = Path(payload['output'])
        score = output / 'score.abc'
        score.write_text('X:1\nK:C\nC D E F|', 'utf-8')
        result = {'files': [], 'scores': [{'path': str(score), 'audio_index': 0, 'mode': 'full'}] if has_score else []}
        (output / 'result.json').write_text(json.dumps(result), 'utf-8')
        return SimpleNamespace(pid=1, returncode=0, wait=AsyncMock(return_value=0))
    monkeypatch.setattr(core.asyncio, 'create_subprocess_exec', subprocess_stub)
    monkeypatch.setattr(core, 'ProcessTree', lambda _: SimpleNamespace(close=lambda: None))
    async def run():
        job = await manager.submit('music', {'operation': operation, 'count': 1, 'workspace': 'Scores', 'title': 'Test', 'mode': 'full'})
        worker = asyncio.create_task(manager.work())
        await asyncio.wait_for(manager.queue.join(), 5)
        worker.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await worker
        return manager.job(job['id'])
    job = asyncio.run(run())
    assert job['status'] == expected
    if expected == 'succeeded':
        assert job['result']['scores'][0]['url'] == f"/v1/jobs/{job['id']}/scores/0"
        app = create_app(tmp_path, token='public')
        with TestClient(app) as client:
            client.headers['Authorization'] = 'Bearer public'
            url = job['result']['scores'][0]['url']
            assert client.get(url).json()['abc'].endswith('C D E F|')
            assert client.get(url + '?download=true').status_code == 200
