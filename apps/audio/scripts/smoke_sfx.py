"""Real GPU smoke test; creates an isolated API data directory under data/."""
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from server.app import create_app

home = Path('data/smoke-sfx') / str(int(time.time()))
with TestClient(create_app(home, token='smoke')) as client:
    client.headers['Authorization'] = 'Bearer smoke'
    state = client.get('/v1/status').json()['services']['sfx']
    assert state['status'] == 'ready', state
    response = client.post('/v1/sfx/generate?wait=false', json={'prompt':'雨水轻轻落在树叶上，没有音乐和说话声。','seconds':3,'count':2,'num_inference_steps':10,'seed':42})
    assert response.status_code == 202, response.text
    job_id = response.json()['id']
    print('Task:', job_id, flush=True)
    deadline = time.monotonic() + 1200
    while time.monotonic() < deadline:
        job = client.get('/v1/jobs/' + job_id).json()
        if job['status'] not in ('queued', 'running'):
            break
        time.sleep(1)
    assert job['status'] == 'succeeded', job
    assert len(job['result']['files']) == 2
    for file in job['result']['files']:
        assert file['sample_rate'] == 48000 and abs(file['duration']-3) < .01
        result = client.get(file['url'])
        assert result.status_code == 200 and result.content[:4] == b'RIFF'
        print('PASS:', file, flush=True)
