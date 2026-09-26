"""Opt-in real-model API smoke test. Requires APP model/runtime setup."""
import argparse
import io
import json
from pathlib import Path
import sys
import tempfile
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from server.app import create_app

parser = argparse.ArgumentParser()
parser.add_argument('input', type=Path, help='Short audio/video fixture (over 2 seconds exercises segmented separation)')
args = parser.parse_args()
with tempfile.TemporaryDirectory(prefix='local-ai-separation-') as home:
    with TestClient(create_app(Path(home), token='smoke-test')) as client:
        client.headers['Authorization'] = 'Bearer smoke-test'
        source = args.input.read_bytes()
        uploaded = client.post('/v1/uploads', files={'file':(args.input.name, source)})
        uploaded.raise_for_status()
        upload_id = uploaded.json()['upload_id']
        cases = [
            ('/v1/separate/file', {'files':{'file':(args.input.name,source)}}, 2, 16000),
            ('/v1/separate', {'json':{'upload_id':upload_id,'segment_seconds':120}}, 2, 16000),
            ('/v1/denoise', {'json':{'upload_id':upload_id}}, 1, 48000),
        ]
        for route, kwargs, expected_count, expected_rate in cases:
            response = client.post(route, **kwargs)
            assert response.status_code == 200, response.text
            files = response.json()['files']
            assert len(files) == expected_count
            if expected_count == 2:
                assert [f['speaker'] for f in files] == [1,2]
            frames = []
            for file in files:
                download = client.get(file['url'])
                assert download.status_code == 200
                with wave.open(io.BytesIO(download.content)) as audio:
                    assert audio.getframerate() == expected_rate
                    assert audio.getnchannels() == 1
                    assert audio.getnframes() > 0
                    frames.append(audio.getnframes())
                    assert any(audio.readframes(audio.getnframes())), 'Unexpected silent output for fixture'
            assert len(set(frames)) == 1
            print(f'PASS {route}: {expected_count} downloadable mono {expected_rate} Hz tracks, {frames[0]} frames', flush=True)
