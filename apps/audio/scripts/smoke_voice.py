"""Real offline tests: preset TTS, clone TTS, uploaded/preset voice conversion."""
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from server.app import create_app

home = Path('data/smoke-voice') / str(int(time.time()))
with TestClient(create_app(home,token='smoke')) as client:
    client.headers['Authorization']='Bearer smoke'
    states = client.get('/v1/status').json()['services']
    for name in ('tts','vc'):
        assert states[name]['status']=='ready', states[name]
    def run(path, body):
        response = client.post(path+'?wait=false',json=body)
        assert response.status_code==202, response.text
        job_id = response.json()['id']
        print(path,job_id,flush=True)
        deadline = time.monotonic()+900
        while time.monotonic()<deadline:
            job = client.get('/v1/jobs/'+job_id).json()
            if job['status'] not in ('running','queued'): break
            time.sleep(1)
        assert job['status']=='succeeded',job
        for f in job['result']['files']:
            data = client.get(f['url'])
            assert data.status_code==200 and data.content[:4]==b'RIFF'
            assert f['duration'] > .5
        print('PASS',job['result'],flush=True)
        return job['result']['files'][0]
    def upload(path):
        return client.post('/v1/uploads',files={'file':(Path(path).name,Path(path).read_bytes())}).json()['upload_id']
    source = run('/v1/tts/generate',{'text':'你好，这是一段本地语音生成测试。','speaker':'vivian'})
    ref = upload('runtimes/voices/uncle_fu.wav')
    run('/v1/tts/generate',{'text':'欢迎使用本地语音服务。','reference_upload_id':ref})
    source_id = upload(source['path'])
    run('/v1/voice/convert',{'source_upload_id':source_id,'target_voice':'serena','diffusion_steps':10})
    run('/v1/voice/convert',{'source_upload_id':source_id,'reference_upload_id':ref,'diffusion_steps':10})
