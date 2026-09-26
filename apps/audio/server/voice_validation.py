"""Lightweight startup checks: never import torch or load model weights."""
import json
from pathlib import Path

def check_models(service, cfg):
    issues = []
    if service == 'tts':
        for key, kind in (('model_dir','custom_voice'), ('clone_model_dir','base')):
            root = Path(cfg[key])
            required = ['config.json','generation_config.json','tokenizer_config.json','vocab.json','merges.txt',
                        'speech_tokenizer/config.json','speech_tokenizer/model.safetensors']
            index = root / 'model.safetensors.index.json'
            if index.is_file():
                required += list(set(json.loads(index.read_text('utf-8'))['weight_map'].values()))
            else:
                required += ['model.safetensors']
            if not cfg[key] or any(not (root / f).resolve().is_relative_to(root.resolve()) or not (root / f).is_file() for f in required):
                issues.append(f'{key}: Qwen3-TTS 模型文件不完整')
            elif json.loads((root / 'config.json').read_text('utf-8')).get('tts_model_type') != kind:
                issues.append(f'{key}: 需要 Qwen3-TTS {kind} 模型')
    else:
        root = Path(cfg['model_dir'])
        required = ['DiT_seed_v2_uvit_whisper_small_wavenet_bigvgan_pruned.pth',
            'config_dit_mel_seed_uvit_whisper_small_wavenet.yml','campplus/campplus_cn_common.bin',
            'whisper/config.json','whisper/preprocessor_config.json','whisper/model.safetensors',
            'bigvgan/config.json','bigvgan/bigvgan_generator.pt']
        if not cfg['model_dir'] or any(not (root / f).is_file() for f in required):
            issues.append('Seed-VC 模型目录不完整，需主模型、Whisper、CAMPPlus 与 BigVGAN')
        if not (Path(cfg['runtime_dir']) / 'inference.py').is_file():
            issues.append('缺少 Seed-VC 运行代码')
    return issues
