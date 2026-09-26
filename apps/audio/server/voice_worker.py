"""Voice adapters imported only inside a disposable inference process."""
import os
from pathlib import Path
import subprocess
import sys

def decode_audio(cfg, source, target, rate, maximum, minimum=.5):
    import soundfile as sf
    subprocess.run([cfg['ffmpeg'], '-nostdin', '-v', 'error', '-y', '-i', str(source),
        '-map','0:a:0','-vn','-t',str(maximum + 1),'-ar',str(rate),'-ac','1',str(target)],
        check=True, timeout=300, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    duration = sf.info(str(target)).duration
    if duration > maximum or duration < minimum:
        raise ValueError(f'音频时长需在 {minimum}–{maximum} 秒之间，当前 {duration:.2f} 秒')
    return str(target)

def write_result(audio, rate, target):
    import numpy as np
    import soundfile as sf
    audio = np.asarray(audio)
    if audio.ndim != 1 or audio.size == 0 or not np.isfinite(audio).all():
        raise RuntimeError('模型返回无效音频')
    sf.write(str(target), audio, rate, subtype='PCM_16')
    return {'path':str(target), 'sample_rate':int(rate), 'duration':len(audio)/rate}

def generate_tts(cfg, request, output):
    if request.get('model') == 'breeze-tts2':
        from breeze_worker import generate_breeze
        return generate_breeze(cfg, request, output)
    import torch
    from qwen_tts import Qwen3TTSModel
    if cfg['device'] == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('文字转语音环境不支持 CUDA')
    reference = request.get('reference_path')
    if reference:
        reference = decode_audio(cfg, reference, output / 'reference.wav', 24000, 30, 3)
    torch.manual_seed(request['seed'])
    model = Qwen3TTSModel.from_pretrained(cfg['clone_model_dir'] if reference else cfg['model_dir'],
        device_map=cfg['device'], dtype=torch.bfloat16 if cfg['device']=='cuda' else torch.float32,
        attn_implementation='sdpa', local_files_only=True)
    kwargs = {'text':request['text'], 'language':request['language'],
        'temperature':request['temperature'], 'max_new_tokens':request['max_new_tokens']}
    with torch.inference_mode():
        if reference:
            wavs, rate = model.generate_voice_clone(**kwargs, ref_audio=reference,
                ref_text=request['reference_text'] or None, x_vector_only_mode=not bool(request['reference_text']))
        else:
            wavs, rate = model.generate_custom_voice(**kwargs, speaker=request['speaker'], instruct=request['instruct'])
    result = write_result(wavs[0], rate, output / 'speech.wav')
    (output / 'reference.wav').unlink(missing_ok=True)
    return {'files':[result], 'model':'qwen3-tts', 'mode':'clone' if reference else 'preset', 'seed':request['seed']}

def convert_voice(cfg, request, output):
    import random
    import numpy as np
    import torch
    import torchaudio
    import yaml
    if cfg['device'] == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('音色转换环境不支持 CUDA')
    source = decode_audio(cfg, request['input_path'], output / 'source.wav', 22050, cfg['max_duration'])
    reference = decode_audio(cfg, request['reference_path'], output / 'reference.wav', 22050, 25, 3)
    runtime = Path(cfg['runtime_dir']).resolve()
    root = Path(cfg['model_dir']).resolve()
    sys.path.insert(0, str(runtime))
    # The upstream utility uses relative caches; constrain them to this task.
    os.chdir(output)
    import inference
    inference.device = torch.device(cfg['device'])
    def local_dependency(repo_id, model_filename, config_filename=None):
        if repo_id == 'funasr/campplus' and model_filename == 'campplus_cn_common.bin' and config_filename is None:
            return str(root / 'campplus/campplus_cn_common.bin')
        raise RuntimeError('未配置本地依赖: ' + repo_id)
    inference.load_custom_model_from_hf = local_dependency
    config = yaml.safe_load((root / 'config_dit_mel_seed_uvit_whisper_small_wavenet.yml').read_text('utf-8'))
    config['model_params']['speech_tokenizer']['name'] = str(root / 'whisper')
    config['model_params']['vocoder']['name'] = str(root / 'bigvgan')
    config_path = output / 'seed-config.yml'
    config_path.write_text(yaml.safe_dump(config), 'utf-8')
    # New torchaudio.save requires TorchCodec. Write validated PCM WAV directly.
    original_save = torchaudio.save
    def save_wave(path, signal, sample_rate, **kwargs):
        return write_result(signal.detach().float().cpu().numpy().reshape(-1), sample_rate, Path(path))
    torchaudio.save = save_wave
    from types import SimpleNamespace
    random.seed(request['seed'])
    np.random.seed(request['seed'])
    torch.manual_seed(request['seed'])
    converted = output / 'converted'
    args = SimpleNamespace(source=source, target=reference, output=str(converted),
        checkpoint=str(root / 'DiT_seed_v2_uvit_whisper_small_wavenet_bigvgan_pruned.pth'),
        config=str(config_path), fp16=cfg['device']=='cuda', f0_condition=False,
        auto_f0_adjust=False, semi_tone_shift=0, diffusion_steps=request['diffusion_steps'],
        length_adjust=request['length_adjust'], inference_cfg_rate=request['inference_cfg_rate'])
    try:
        inference.main(args)
    finally:
        torchaudio.save = original_save
    import soundfile as sf
    paths = list(converted.glob('*.wav'))
    if len(paths) != 1:
        raise RuntimeError('Seed-VC 未返回有效结果')
    audio, rate = sf.read(str(paths[0]))
    result = write_result(audio, rate, output / 'converted.wav')
    (output / 'source.wav').unlink(missing_ok=True)
    (output / 'reference.wav').unlink(missing_ok=True)
    paths[0].unlink()
    return {'files':[result], 'model':'Seed-VC', 'seed':request['seed']}
