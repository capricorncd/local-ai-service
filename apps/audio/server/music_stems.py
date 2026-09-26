"""Music vocals/accompaniment separation, using the existing music Python runtime."""
from pathlib import Path
import os
import subprocess

def separate_chunks(model, waveform, sample_rate, device, seconds=10, overlap=1):
    import torch
    frames = waveform.shape[-1]
    segment = int(seconds * sample_rate)
    fade = int(overlap * sample_rate)
    hop = segment - fade
    if frames == 0 or hop <= 0:
        raise ValueError('Invalid separation input')
    output = torch.zeros(len(model.sources), waveform.shape[0], frames)
    weights = torch.zeros(frames)
    with torch.inference_mode():
        for start in range(0, frames, hop):
            end = min(start + segment, frames)
            chunk = waveform[:, start:end]
            # Fixed chunks avoid unstable FFT padding for very short final sections.
            padded = torch.nn.functional.pad(chunk, (0, segment - chunk.shape[-1]))
            stems = model(padded.unsqueeze(0).to(device))[0, :, :, :end-start].cpu()
            weight = torch.ones(end-start)
            length = min(fade, end-start)
            if start:
                weight[:length] *= torch.linspace(1/(length+1), 1, length)
            if end < frames:
                weight[-length:] *= torch.linspace(1, 1/(length+1), length)
            output[:, :, start:end] += stems * weight
            weights[start:end] += weight
            print(f'歌曲分离进度 {end / frames:.0%}', flush=True)
            if end == frames:
                break
    return output / weights.clamp_min(1e-8)

def separate_music(cfg, request, output):
    import torch
    import soundfile as sf
    import numpy as np
    from torchaudio.models import hdemucs_high
    from music_names import song_filename
    checkpoint = Path(cfg['stems_model_path'])
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    if not checkpoint.is_file():
        print('首次使用，下载官方 HDemucs 歌曲分离模型…', flush=True)
        temporary = checkpoint.with_suffix('.part')
        torch.hub.download_url_to_file('https://download.pytorch.org/torchaudio/models/hdemucs_high_trained.pt', str(temporary))
        # Reject incomplete/unreadable downloads before making them the active checkpoint.
        torch.load(str(temporary), map_location='cpu', weights_only=True)
        temporary.replace(checkpoint)
    device = cfg['device']
    if device == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('当前音乐运行环境不支持 CUDA')
    decoded = output / 'source.wav'
    subprocess.run([cfg['ffmpeg'], '-nostdin', '-v', 'error', '-y', '-i', request['input_path'],
                    '-map', '0:a:0', '-vn', '-ar', '44100', '-ac', '2', '-t', '901', str(decoded)],
                   check=True, timeout=300, creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    audio, rate = sf.read(str(decoded), dtype='float32', always_2d=True)
    if not len(audio) or len(audio)/rate > 900 or not np.isfinite(audio).all():
        raise ValueError('歌曲分离支持 0–900 秒的有效音频')
    waveform = torch.from_numpy(audio.T.copy())
    reference = waveform.mean(0)
    mean, std = reference.mean(), reference.std(unbiased=False).clamp_min(1e-8)
    model = hdemucs_high(sources=['drums', 'bass', 'other', 'vocals'])
    model.load_state_dict(torch.load(str(checkpoint), map_location='cpu', weights_only=True))
    model.to(device).eval()
    stems = separate_chunks(model, (waveform-mean)/std, rate, device) * std
    # Allocate the removed DC component across stems to preserve their summed baseline.
    stems += mean / len(model.sources)
    vocals = stems[model.sources.index('vocals')]
    accompaniment = stems[[i for i,s in enumerate(model.sources) if s!='vocals']].sum(0)
    peak = max(float(vocals.abs().max()), float(accompaniment.abs().max()), 1.0)
    files=[]
    for index,(tag,signal) in enumerate([('vocals',vocals),('instrumental',accompaniment)]):
        title=request['song_titles'][index]
        path=output/(song_filename(title)+'.wav')
        samples=(signal/peak).T.numpy()
        if not np.isfinite(samples).all():raise RuntimeError('分离模型输出无效音频')
        sf.write(str(path), samples, rate, subtype='PCM_16')
        files.append({'path':str(path),'title':title,'tag':tag,'sample_rate':rate,'duration':len(samples)/rate,
                      'source_job_id':request['source_job_id'],'source_audio_index':request['source_audio_index']})
    decoded.unlink(missing_ok=True)
    return {'files':files,'model':'HDemucs','operation':'separate'}
