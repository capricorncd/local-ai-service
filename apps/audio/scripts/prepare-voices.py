"""Generate app-owned preset references with Qwen3-TTS; run with runtimes/tts Python."""
import os
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_HOME'] = str(ROOT / 'runtimes/hf-cache')
import torch
import soundfile as sf
import numpy as np
from qwen_tts import Qwen3TTSModel
from server.voices import VOICES

texts = {
    'Chinese':'你好，欢迎使用本地语音服务。今天的天气很好，让我们用清晰自然的声音，记录生活中的每一个精彩瞬间。',
    'English':'Hello, welcome to the local voice service. It is a beautiful day. Let us share a story and enjoy the wonderful moments of everyday life.',
    'Japanese':'こんにちは。ローカル音声サービスへようこそ。今日はとてもいい天気ですね。自然な声で、毎日の素敵な出来事を伝えましょう。',
    'Korean':'안녕하세요. 음성 서비스에 오신 것을 환영합니다. 오늘은 날씨가 참 좋네요. 자연스러운 목소리로 일상의 소중한 순간을 함께 나누어요.',
}
directory = ROOT / 'runtimes/voices'
directory.mkdir(exist_ok=True)
missing = [v for v in VOICES if not (directory / (v['id']+'.wav')).is_file()]
if missing:
    model = Qwen3TTSModel.from_pretrained(str(ROOT/'runtimes/models/Qwen3-TTS-12Hz-1.7B-CustomVoice'),
        device_map='cuda', dtype=torch.bfloat16, attn_implementation='sdpa', local_files_only=True)
    for voice in missing:
        torch.manual_seed(42)
        text = texts[voice['language']]
        wavs, rate = model.generate_custom_voice(text=text, language=voice['language'], speaker=voice['id'], max_new_tokens=512)
        audio = np.asarray(wavs[0])
        assert np.isfinite(audio).all() and 3 <= len(audio)/rate <= 25
        sf.write(str(directory / (voice['id']+'.wav')), audio, rate, subtype='PCM_16')
        (directory / (voice['id']+'.txt')).write_text(text, 'utf-8')
        print('Prepared', voice['id'], len(audio)/rate, flush=True)
