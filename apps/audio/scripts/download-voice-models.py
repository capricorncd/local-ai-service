from pathlib import Path
from huggingface_hub import snapshot_download
root = Path(__file__).resolve().parents[1] / 'runtimes/models'
for name in ('Qwen3-TTS-12Hz-1.7B-CustomVoice','Qwen3-TTS-12Hz-1.7B-Base'):
    snapshot_download('Qwen/'+name, local_dir=str(root/name))
vc = root/'Seed-VC'
snapshot_download('Plachta/Seed-VC', local_dir=str(vc), allow_patterns=['DiT_seed_v2_uvit_whisper_small_wavenet_bigvgan_pruned.pth','config_dit_mel_seed_uvit_whisper_small_wavenet.yml'])
snapshot_download('funasr/campplus',local_dir=str(vc/'campplus'),allow_patterns=['campplus_cn_common.bin'])
snapshot_download('openai/whisper-small',local_dir=str(vc/'whisper'),allow_patterns=['config.json','preprocessor_config.json','model.safetensors'])
snapshot_download('nvidia/bigvgan_v2_22khz_80band_256x',local_dir=str(vc/'bigvgan'),allow_patterns=['config.json','bigvgan_generator.pt'])
