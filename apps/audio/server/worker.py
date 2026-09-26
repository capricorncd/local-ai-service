"""One inference task per process. No torch import in the API server or probe."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

def probe(service, cfg):
    required = ['torch', 'soundfile']
    if service == 'music':
        required += ['torchaudio', 'safetensors', 'transformers', 'comfy_kitchen', 'comfy_aimdo', 'av', 'scipy', 'einops', 'sentencepiece']
        if not (Path(cfg['runtime_dir']) / 'comfy_extras' / 'nodes_yue2.py').is_file():
            raise RuntimeError('运行目录缺少 comfy_extras/nodes_yue2.py')
    elif service == 'auk':
        required += ['auk', 'transformers', 'qwen_omni_utils', 'omegaconf', 'torchdiffeq', 'x_transformers']
        if not shutil.which(cfg['ffmpeg']):
            raise RuntimeError('找不到 FFmpeg 可执行文件')
    elif service == 'sfx':
        required += ['moss_soundeffect_v2', 'transformers', 'diffusers', 'torchaudio', 'audiotools']
    elif service in ('tts', 'vc'):
        required += ['qwen_tts'] if service == 'tts' else ['librosa', 'munch', 'yaml', 'transformers', 'torchaudio']
        if not shutil.which(cfg['ffmpeg']):
            raise RuntimeError('找不到 FFmpeg 可执行文件')
    else:
        required += ['clearvoice']
        if not shutil.which(cfg['ffmpeg']):
            raise RuntimeError('找不到 FFmpeg 可执行文件')
    missing = [name for name in required if importlib.util.find_spec(name) is None]
    if missing:
        raise RuntimeError('Python 环境缺少依赖: ' + ', '.join(missing))

def music(cfg, request, output):
    if request.get('operation') == 'transcribe':
        from score_worker import transcribe_music
        return transcribe_music(cfg, request, output)
    if request.get('operation') == 'separate':
        from music_stems import separate_music
        return separate_music(cfg, request, output)
    from music_names import song_titles, song_filename
    titles = request.get('song_titles') or song_titles(request.get('title', ''), request['count'])
    sys.path.insert(0, cfg['runtime_dir'])
    # ComfyUI parses argv at import time. Never pass the worker request path to it.
    sys.argv = [sys.argv[0], '--disable-all-custom-nodes']
    if cfg['device'] == 'cpu':
        sys.argv += ['--cpu']
    import comfy.options
    comfy.options.enable_args_parsing()
    import torch
    import soundfile as sf
    import comfy.sd
    import nodes
    from comfy_extras.nodes_yue2 import YuE2GenerateABC, YuE2GenerateMusic, EmptyYuE2LatentAudio
    from comfy_extras.nodes_audio import VAEDecodeAudioTiled

    def values(result):
        return result.result if hasattr(result, 'result') else result

    if request.get('reference_audio_path'):
        from score_worker import extract_reference_score
        request['abc'] = extract_reference_score(cfg, request, output)
        (output / 'reference.abc').write_text(request['abc'], 'utf-8')
        print('参考曲谱提取完成，开始生成新版本', flush=True)
    model, clip, vae = comfy.sd.load_checkpoint_guess_config(cfg['model_path'], output_vae=True, output_clip=True)[:3]
    from lora_worker import apply_music_loras
    model, clip, loras = apply_music_loras(model, clip, request)
    files = []
    scores = []
    with torch.inference_mode():
        for index in range(request['count']):
            seed = request['seed'] + index
            mode = request['mode']
            abc = request.get('abc') or ''
            if mode != 'off' and not abc:
                abc = values(YuE2GenerateABC.execute(clip, request['style'], request['lyrics'], seed, mode, 8192))[0]
            positive, seconds = values(YuE2GenerateMusic.execute(clip, request['style'], request['lyrics'], seed, 'full' if mode == 'off' else mode, request['max_duration'], request['temperature'], request['top_p'], request['top_k'], request['repetition_penalty'], abc))
            negative = nodes.ConditioningZeroOut().zero_out(positive)[0]
            latent = values(EmptyYuE2LatentAudio.execute(seconds, 1))[0]
            samples = nodes.KSampler().sample(model, seed, request['steps'], request['cfg'], 'dpm_2', 'sgm_uniform', positive, negative, latent)[0]
            audio = values(VAEDecodeAudioTiled.execute(vae, samples, 512, 64))[0]
            title = titles[index]
            filename = output / (song_filename(title) + '.wav')
            sf.write(str(filename), audio['waveform'][0].float().cpu().numpy().T, audio['sample_rate'], subtype='PCM_16')
            if request.get('generate_score'):
                if not abc.strip():
                    raise RuntimeError('模型未返回曲谱，请重试或更换随机种子')
                score_path = output / (song_filename(title) + '.abc')
                score_path.write_text(abc, 'utf-8')
                scores.append({'path': str(score_path), 'title': title, 'audio_index': index, 'format': 'abc', 'mode': mode})
            files.append({'path': str(filename), 'title': title, 'seed': seed, 'sample_rate': audio['sample_rate'], 'duration': seconds})
    return {'files': files, 'scores': scores, 'model': 'YuE2', 'count': len(files), 'lora_provider':request.get('lora_provider','none'), 'loras':loras}

def auk(cfg, request, output):
    from auk_worker import generate
    return generate(cfg, request, output)

def sfx(cfg, request, output):
    # Eager inference avoids Triton/compiler dependencies on Windows.
    os.environ['TORCHDYNAMO_DISABLE'] = '1'
    import torch
    import soundfile as sf
    from moss_soundeffect_v2 import MossSoundEffectPipeline
    if cfg['device'] == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('当前音效环境不支持 CUDA')
    pipeline = MossSoundEffectPipeline.from_pretrained(
        cfg['model_dir'], device=cfg['device'], torch_dtype=torch.bfloat16,
        local_files_only=True)
    files = []
    with torch.inference_mode():
        for index in range(request['count']):
            seed = request['seed'] + index
            audio = pipeline(prompt=request['prompt'], negative_prompt=request['negative_prompt'],
                seconds=request['seconds'], num_inference_steps=request['num_inference_steps'],
                cfg_scale=request['cfg_scale'], sigma_shift=request['sigma_shift'], seed=seed)
            if audio.ndim != 3 or audio.shape[0:2] != (1, 1) or not torch.isfinite(audio).all():
                raise RuntimeError('音效模型返回无效的音频数据')
            target = output / f'sound-{index + 1}.wav'
            sf.write(str(target), audio[0].float().cpu().numpy().T, pipeline.sample_rate, subtype='PCM_16')
            info = sf.info(str(target))
            files.append({'path': str(target), 'seed': seed, 'sample_rate': info.samplerate, 'duration': info.duration})
    return {'files': files, 'model': 'MOSS-SoundEffect-v2.0', 'count': len(files)}

def tts(cfg, request, output):
    from voice_worker import generate_tts
    return generate_tts(cfg, request, output)

def vc(cfg, request, output):
    from voice_worker import convert_voice
    return convert_voice(cfg, request, output)

def denoise(cfg, request, output):
    return process_speech(cfg, request, output, separate=False)

def separation(cfg, request, output):
    return process_speech(cfg, request, output, separate=True)

def process_speech(cfg, request, output, separate):
    cfg = {**cfg, **{key: request[key] for key in ('segment_seconds','max_duration') if request.get(key) is not None}}
    os.environ['PATH'] = str(Path(cfg['ffmpeg']).resolve().parent) + os.pathsep + os.environ.get('PATH', '')
    sys.argv = [sys.argv[0]]
    import torch
    if cfg['device'] == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('当前 Python 环境不支持 CUDA，请改用 CPU 或安装 CUDA 版 PyTorch')
    from clearvoice.network_wrapper import network_wrapper
    from clearvoice.networks import CLS_MossFormer2_SE_48K, CLS_MossFormer2_SS_16K, SpeechModel
    model_name = 'MossFormer2_SS_16K' if separate else 'MossFormer2_SE_48K'
    sample_rate = 16000 if separate else 48000

    # ClearVoice's public constructor loads the model immediately; override args
    # before constructing the model so the local checkpoint path is truly used.
    wrapper = network_wrapper()
    wrapper.model_name = model_name
    if separate:
        wrapper.load_args_ss()
    else:
        wrapper.load_args_se()
    args = wrapper.args
    args.checkpoint_dir = cfg['model_dir']
    args.use_cuda = int(cfg['device'] == 'cuda')
    args.task = 'speech_separation' if separate else 'speech_enhancement'
    args.network = model_name
    args.one_time_decode_length = cfg['segment_seconds']
    args.sampling_rate = sample_rate
    if separate:
        args.num_spks = 2
    # Upstream otherwise silently falls back to downloading or partial weights.
    def no_download(self, name):
        raise RuntimeError('缺少本地权重，禁止自动下载: ' + name)
    def strict_load(self, model, path, model_key=None):
        checkpoint = torch.load(path, map_location='cpu', weights_only=True)
        state = checkpoint.get(model_key, checkpoint)
        state = {k.removeprefix('module.'): v for k, v in state.items()}
        model.load_state_dict(state, strict=True)
    SpeechModel.download_model = no_download
    SpeechModel._load_model = strict_load
    if cfg['device'] == 'cuda':
        SpeechModel.get_free_gpu = lambda self: 0
    model = (CLS_MossFormer2_SS_16K if separate else CLS_MossFormer2_SE_48K)(args)
    # Decode video/audio with a bounded duration; refuse rather than truncate.
    clean_input = output / 'input-normalized.wav'
    subprocess.run([cfg['ffmpeg'], '-nostdin', '-v', 'error', '-y', '-i', request['input_path'], '-map', '0:a:0', '-vn', '-t', str(cfg['max_duration'] + 1), '-ar', str(sample_rate), '-ac', '1', str(clean_input)], check=True, timeout=300, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    import soundfile as sf
    if sf.info(str(clean_input)).duration > cfg['max_duration']:
        raise RuntimeError('音频超过配置的最大处理时长')
    result = model.process(str(clean_input), online_write=False)
    files = []
    if separate:
        import numpy as np
        if not isinstance(result, list) or len(result) != 2:
            raise RuntimeError('分离模型必须返回两条说话人音轨')
        input_frames = sf.info(str(clean_input)).frames
        for index, signal in enumerate(result):
            waveform = np.asarray(signal)
            if waveform.shape != (1, input_frames) or not np.isfinite(waveform).all():
                raise RuntimeError('分离音轨长度、声道或采样值无效')
            target = output / f'speaker-{index + 1}.wav'
            sf.write(str(target), waveform[0], sample_rate, subtype='PCM_16')
            files.append({'path': str(target), 'speaker': index + 1, 'sample_rate': sample_rate, 'duration': input_frames / sample_rate})
    else:
        target = output / 'denoised.wav'
        model.write(str(target))
        info = sf.info(str(target))
        files.append({'path': str(target), 'sample_rate': info.samplerate, 'duration': info.duration})
    clean_input.unlink(missing_ok=True)
    return {'files': files, 'model': model_name}

if __name__ == '__main__':
    if sys.argv[1] == '--probe':
        probe(sys.argv[2], json.loads(sys.argv[3]))
    else:
        payload = json.loads(Path(sys.argv[1]).read_text('utf-8'))
        cfg = payload['config']
        os.environ['HF_HUB_OFFLINE'] = '1'
        os.environ['TRANSFORMERS_OFFLINE'] = '1'
        os.environ['HF_HOME'] = str(Path(__file__).resolve().parents[1] / 'runtimes/hf-cache')
        os.environ['MPLCONFIGDIR'] = str(Path(__file__).resolve().parents[1] / 'runtimes/matplotlib-cache')
        if cfg['device'] == 'cpu':
            os.environ['CUDA_VISIBLE_DEVICES'] = ''
        output = Path(payload['output'])
        result = globals()[payload['service']](cfg, payload['request'], output)
        (output / 'result.json').write_text(json.dumps(result), 'utf-8')
