"""Opt-in real GPU integration check against an already-running development API."""
import json
from pathlib import Path
import time
import httpx

root = Path(__file__).resolve().parents[1]
headers = {'Authorization': 'Bearer ' + (root / 'data/api-token').read_text().strip()}
with httpx.Client(base_url='http://127.0.0.1:19876', headers=headers, timeout=120) as client:
    cfg = client.get('/v1/config').json()
    cfg['denoise']['model_dir'] = str(root / 'runtimes/models/MossFormer2_SE_48K')
    client.put('/v1/config', json=cfg).raise_for_status()
    client.post('/v1/services/denoise/restart').raise_for_status()
    with (root / 'data/smoke-denoise/video.mp4').open('rb') as f:
        upload = client.post('/v1/uploads', files={'file': ('video.mp4', f, 'video/mp4')})
    upload.raise_for_status()
    music = client.post('/v1/music/generate?wait=false', json={'lyrics':'[Verse]\nHello world, a brand new day','style':'English acoustic pop','mode':'off','count':2,'steps':4,'max_duration':3})
    music.raise_for_status()
    denoise = client.post('/v1/denoise?wait=false', json={'upload_id':upload.json()['upload_id']})
    denoise.raise_for_status()
    ids = [music.json()['id'], denoise.json()['id']]
    deadline = time.monotonic() + 300
    while ids and time.monotonic() < deadline:
        for job_id in ids.copy():
            job = client.get('/v1/jobs/' + job_id).json()
            if job['status'] in ('failed','cancelled'):
                raise RuntimeError(job)
            if job['status'] == 'succeeded':
                files = job['result']['files']
                assert len(files) == (2 if job['service'] == 'music' else 1)
                for item in files:
                    response = client.get(item['url'])
                    response.raise_for_status()
                    assert response.content[:4] == b'RIFF'
                    assert len(response.content) > 1000
                print(f"PASS {job['service']}: {len(files)} downloadable audio files", flush=True)
                ids.remove(job_id)
        time.sleep(1)
    assert not ids, 'Integration timed out'
