from pathlib import Path
import json
import subprocess


def check_models(cfg):
    root = Path(cfg['model_dir'])
    issues = []
    if not all((root / name).is_file() for name in ('config.yaml', 'vae.safetensors')) or not any((root / name).is_file() for name in ('auk_base.safetensors','auk_flash.safetensors')):
        issues.append('AuK 目录需要 config.yaml、vae.safetensors 和 Base 或 Flash 权重')
    qwen = Path(cfg['qwen_dir'])
    if not all((qwen / name).is_file() for name in ('config.json','preprocessor_config.json','tokenizer_config.json')):
        issues.append('缺少完整 Qwen2.5-Omni-3B 模型目录')
    else:
        index = qwen / 'model.safetensors.index.json'
        try:
            names = set(json.loads(index.read_text('utf-8'))['weight_map'].values()) if index.is_file() else {'model.safetensors'}
            if not names or any(not (qwen / n).resolve().is_relative_to(qwen.resolve()) or not (qwen / n).is_file() for n in names):
                issues.append('Qwen2.5-Omni-3B 权重不完整')
        except (ValueError, KeyError, OSError):
            issues.append('Qwen 模型索引无效')
    return issues


def generate(cfg, request, output):
    import torch
    import soundfile as sf
    from auk.infer.infer_auk import AukInfer, save_audio
    root = Path(cfg['model_dir'])
    checkpoint = root / ('auk_base.safetensors' if (root / 'auk_base.safetensors').is_file() else 'auk_flash.safetensors')
    content = [{'type':'text', 'text':request['instruction']}]
    source_seconds = 0
    if request.get('input_path'):
        source = output / 'source.wav'
        command = [cfg['ffmpeg'],'-nostdin','-y','-v','error','-ss',str(request['clip_start']),'-i',request['input_path'],'-t',str(request['clip_seconds']),'-map','0:a:0','-vn','-ac','1','-ar','24000',str(source)]
        subprocess.run(command, check=True, capture_output=True, timeout=120)
        source_seconds = sf.info(str(source)).duration
        if source_seconds <= 0 or source_seconds + request['gen_seconds'] > 30.01:
            raise RuntimeError('输入与输出总时长必须在 30 秒内')
        content.append({'type':'audio','audio':str(source)})
    engine = AukInfer(str(root / 'config.yaml'), str(checkpoint), device=cfg['device'], dtype='bf16' if cfg['device']=='cuda' else 'fp32', qwen_path=cfg['qwen_dir'], cpu_offload=cfg['cpu_offload'] and cfg['device']=='cuda')
    with torch.inference_mode():
        audio, rate = engine.generate([{'role':'user','content':content}], gen_seconds=request['gen_seconds'], nfe=request['steps'], cfg_strength=request['cfg'], seed=request['seed'])
    if not torch.isfinite(audio).all():
        raise RuntimeError('AuK 输出包含无效音频数值')
    target = output / 'edited.wav'
    save_audio(audio, rate, str(target))
    info = sf.info(str(target))
    return {'files':[{'path':str(target),'sample_rate':info.samplerate,'duration':info.duration,'seed':request['seed']}], 'model':'AuK-Flash' if engine.is_flash else 'AuK', 'task':request['task'], 'source_seconds':source_seconds}
