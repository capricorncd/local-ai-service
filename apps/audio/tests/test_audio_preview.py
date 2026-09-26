import base64
import io
import subprocess
import wave
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from server.app import create_app


def test_video_preview_extracts_first_audio_track_and_rejects_silent_video(tmp_path):
    ffmpeg = Path(__file__).resolve().parents[1] / 'runtimes/ffmpeg/bin/ffmpeg.exe'
    if not ffmpeg.is_file():
        pytest.skip('Bundled FFmpeg is required for media integration test')
    video = tmp_path / 'reference with spaces.mkv'
    subprocess.run([str(ffmpeg), '-v', 'error', '-f', 'lavfi', '-i', 'color=size=16x16:rate=1',
                    '-f', 'lavfi', '-i', 'sine=frequency=440:duration=1', '-t', '1',
                    '-c:v', 'ffv1', '-c:a', 'pcm_s16le', str(video)], check=True, timeout=30)
    silent = tmp_path / 'silent.mp4'
    subprocess.run([str(ffmpeg), '-v', 'error', '-f', 'lavfi', '-i', 'color=size=16x16:rate=1',
                    '-t', '1', '-c:v', 'mpeg4', str(silent)], check=True, timeout=30)
    with TestClient(create_app(tmp_path / 'app', token='secret')) as client:
        client.headers['Authorization'] = 'Bearer secret'
        for service in ('music', 'tts', 'vc', 'auk', 'denoise', 'separation'):
            getattr(client.app.state.manager.active, service).ffmpeg = str(ffmpeg)
        uploaded = client.post('/v1/uploads', files={'file': (video.name, video.read_bytes())}).json()['upload_id']
        endpoint = f'/v1/uploads/{uploaded}/audio-preview'
        assert client.post(endpoint, headers={'Authorization': ''}).status_code == 401
        assert client.post('/v1/uploads/missing.mp4/audio-preview').status_code == 404
        assert client.post(endpoint + '?service=unknown').status_code == 422
        for service in ('music', 'tts', 'vc', 'auk', 'denoise', 'separation'):
            response = client.post(endpoint + f'?service={service}')
            assert response.status_code == 200, response.text
            with wave.open(io.BytesIO(base64.b64decode(response.json()['audio_base64']))) as audio:
                assert audio.getnchannels() == 1
                assert audio.getframerate() == 24000
                assert .9 <= audio.getnframes() / 24000 <= 1.1
        uploaded = client.post('/v1/uploads', files={'file': (silent.name, silent.read_bytes())}).json()['upload_id']
        assert client.post(f'/v1/uploads/{uploaded}/audio-preview').status_code == 422


@pytest.mark.parametrize('seconds,expected', [(300, 300), (901, 900)])
def test_video_preview_keeps_five_minutes_and_caps_at_fifteen(tmp_path, seconds, expected):
    ffmpeg = Path(__file__).resolve().parents[1] / 'runtimes/ffmpeg/bin/ffmpeg.exe'
    if not ffmpeg.is_file():
        pytest.skip('Bundled FFmpeg is required for media integration test')
    video = tmp_path / 'long-reference.mkv'
    subprocess.run([str(ffmpeg), '-v', 'error', '-f', 'lavfi', '-i', 'color=size=16x16:rate=1',
                    '-f', 'lavfi', '-i', f'sine=frequency=440:sample_rate=24000:duration={seconds}',
                    '-t', str(seconds), '-c:v', 'ffv1', '-c:a', 'flac', str(video)],
                   check=True, timeout=60)
    with TestClient(create_app(tmp_path / 'app', token='secret')) as client:
        client.headers['Authorization'] = 'Bearer secret'
        client.app.state.manager.active.music.ffmpeg = str(ffmpeg)
        uploaded = client.post('/v1/uploads', files={'file': (video.name, video.read_bytes())}).json()['upload_id']
        response = client.post(f'/v1/uploads/{uploaded}/audio-preview?service=music')
        assert response.status_code == 200, response.text
        with wave.open(io.BytesIO(base64.b64decode(response.json()['audio_base64']))) as audio:
            assert abs(audio.getnframes() / audio.getframerate() - expected) < .1
