"""Breeze adapter; weights stay offline and inference runs in its own environment."""
from pathlib import Path
import json
import os
import subprocess
import sys

def check_breeze(cfg):
    issues = []
    if not Path(cfg['python']).is_file():
        issues.append('TTS 共用 Python 环境未安装')
    if not (Path(cfg['breeze_runtime_dir']) / 'infer.py').is_file():
        issues.append('Breeze 推理代码目录不存在')
    root = Path(cfg['breeze_model_dir'])
    required = ['config.json', 'tokenizer_config.json', 'audio_tokenizer/config.json']
    for folder in [root, root / 'audio_tokenizer']:
        index = folder / 'model.safetensors.index.json'
        try:
            weights = list(set(json.loads(index.read_text('utf-8'))['weight_map'].values())) if index.is_file() else ['model.safetensors']
            if any(not (folder / f).resolve().is_relative_to(folder.resolve()) or not (folder / f).is_file() for f in weights):
                issues.append('Breeze 模型权重不完整，请下载模型')
        except (ValueError, KeyError, OSError):
            issues.append('Breeze 模型索引无效')
    if any(not (root / f).is_file() for f in required):
        issues.append('Breeze 模型配置不完整，请下载模型')
    if not Path(cfg['ffmpeg']).is_file():
        issues.append('FFmpeg 程序不存在')
    if not cfg['breeze_output_dir']:
        issues.append('请配置 Breeze 输出目录')
    return list(dict.fromkeys(issues))

def generate_breeze(cfg, request, output):
    import torch
    import soundfile as sf
    from voice_worker import decode_audio, write_result
    if not torch.cuda.is_available():
        raise RuntimeError('Breeze TTS 2 需要支持 CUDA 的独立运行环境')
    instruction = str(request.get('instruct') or '').strip()
    cfg_scale = 1.0 if request.get('reference_path') and not instruction else request['cfg_scale']
    target = output / 'speech.wav'
    command = [sys.executable, str(Path(cfg['breeze_runtime_dir']) / 'infer.py'), cfg['breeze_model_dir'],
               '--text', request['text'], '--seed', str(request['seed']), '--cfg-scale', str(cfg_scale),
               '--output', str(target)]
    if instruction:
        command += ['--instruction', instruction]
    if request.get('reference_path'):
        reference = decode_audio(cfg, request['reference_path'], output / 'reference.wav', 24000, 30, 3)
        command += ['--ref-audio', reference, '--ref-text', request['reference_text']]
    if cfg['breeze_fast']:
        command.append('--fast-all')
    log_path = output / 'breeze.log'
    with log_path.open('wb') as log:
        process = subprocess.run(command, cwd=cfg['breeze_runtime_dir'], timeout=cfg['timeout_seconds'],
                                 stdout=log, stderr=subprocess.STDOUT,
                                 creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    if process.returncode:
        detail = log_path.read_text('utf-8', errors='replace')[-6000:].strip()
        raise RuntimeError(detail or f'Breeze inference exited with code {process.returncode}; see {log_path}')
    audio, rate = sf.read(str(target))
    result = write_result(audio, rate, target)
    (output / 'reference.wav').unlink(missing_ok=True)
    mode = 'direction' if request.get('reference_path') and instruction else 'clone' if request.get('reference_path') else 'design'
    return {'files': [result], 'model': 'breeze-tts2', 'mode': mode, 'seed': request['seed']}
