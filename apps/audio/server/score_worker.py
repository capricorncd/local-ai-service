"""Reference audio transcription, without loading the music generation checkpoint."""
import os
import subprocess
import sys


def extract_reference_score(cfg, request, output):
    sys.path.insert(0, cfg['runtime_dir'])
    sys.argv = [sys.argv[0], '--disable-all-custom-nodes']
    if cfg['device'] == 'cpu':
        sys.argv += ['--cpu']
    import comfy.options
    comfy.options.enable_args_parsing()
    import torch
    import soundfile as sf
    import gc
    import comfy.utils
    import comfy.model_management
    from comfy.audio_encoders.audio_encoders import load_audio_encoder_from_sd
    print('正在使用 SheetSage2 将原音频转为参考曲谱', flush=True)
    reference_wav = output / 'reference-input.wav'
    subprocess.run([cfg['ffmpeg'], '-nostdin', '-v', 'error', '-y', '-i', request['reference_audio_path'], '-map', '0:a:0', '-vn', '-t', '901', '-ar', '44100', '-ac', '2', str(reference_wav)], check=True, timeout=300, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    try:
        waveform, rate = sf.read(str(reference_wav), dtype='float32', always_2d=True)
    finally:
        reference_wav.unlink(missing_ok=True)
    if not len(waveform) or len(waveform) / rate > 900:
        raise RuntimeError('参考音频需为 0–900 秒的有效歌曲')
    encoder = load_audio_encoder_from_sd(comfy.utils.load_torch_file(cfg['encoder_path'], safe_load=True))
    with torch.inference_mode():
        abc_list = encoder.generate_abc(torch.from_numpy(waveform.T).unsqueeze(0), rate, melody_only=request['mode'] == 'melody')
    if not abc_list or not abc_list[0].strip():
        raise RuntimeError('SheetSage2 未能提取有效曲谱')
    abc = abc_list[0]
    comfy.model_management.unload_all_models()
    del encoder, waveform
    gc.collect()
    comfy.model_management.soft_empty_cache()

    return abc


def transcribe_music(cfg, request, output):
    from music_names import song_titles, song_filename
    abc = extract_reference_score(cfg, request, output)
    title = (request.get('song_titles') or song_titles(request.get('title', ''), 1))[0]
    path = output / (song_filename(title) + '.abc')
    path.write_text(abc, 'utf-8')
    return {'files': [], 'scores': [{'path': str(path), 'title': title,
            'audio_index': 0, 'format': 'abc', 'mode': request['mode']}],
            'model': 'SheetSage2', 'count': 1}
