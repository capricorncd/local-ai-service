"""Read-only LoRA catalogue; no torch import and no execution of metadata."""
import json
from pathlib import Path
import struct
from fastapi import HTTPException

PROVIDERS = [
    {'id':'none','name':'不使用 LoRA','targets':[]},
    {'id':'speedyrulz','name':'speedyrulz · 声学 / 规划 LoRA','targets':['acoustic','planner'],
     'url':'https://github.com/speedyrulz/ComfyUI-YuE2-Trainer'},
    {'id':'starnodes2024','name':'Starnodes2024 · 声学 LoRA','targets':['acoustic'],
     'url':'https://github.com/Starnodes2024/ComfyUI-YuE2-Trainer', 'recommended_mode':'off'},
]

def resolve_lora(directory, name):
    root = Path(directory).resolve()
    relative = Path(name)
    path = (root / relative).resolve()
    if not directory or relative.is_absolute() or relative.drive or not path.is_relative_to(root) or path.suffix.lower() != '.safetensors':
        raise HTTPException(400, 'LoRA 必须是配置目录中的 safetensors 文件')
    if not path.is_file():
        raise HTTPException(404, 'LoRA 文件不存在')
    return path

def inspect_lora(path):
    with path.open('rb') as file:
        size = file.read(8)
        if len(size) != 8:
            raise ValueError('无效的 safetensors 文件')
        length = struct.unpack('<Q', size)[0]
        if not 2 <= length <= 16*1024*1024 or length > path.stat().st_size-8:
            raise ValueError('无效的 safetensors 文件头')
        header = json.loads(file.read(length))
    if not isinstance(header, dict):
        raise ValueError('无效的 LoRA 文件头')
    targets = []
    for target, prefix in (('acoustic','diffusion_model.'),('planner','text_encoders.')):
        if any(key.startswith(prefix) and key.endswith('.lora_up.weight') and key[:-len('.lora_up.weight')]+'.lora_down.weight' in header for key in header):
            targets.append(target)
    if not targets:
        raise ValueError('不是支持的原生 ComfyUI LoRA 格式，请使用训练器的原生格式导出')
    return targets

def catalog(directory):
    root = Path(directory)
    files = []
    if directory and root.is_dir():
        for path in sorted(root.rglob('*.safetensors')):
            if not path.resolve().is_relative_to(root.resolve()):
                continue
            item = {'id':path.relative_to(root).as_posix(), 'name':path.stem, 'targets':[], 'error':None}
            try:
                item['targets'] = inspect_lora(path)
            except (ValueError, OSError, TypeError) as error:
                item['error'] = str(error)
            files.append(item)
    return {'providers':PROVIDERS, 'directory':directory, 'directory_exists':bool(directory and root.is_dir()), 'files':files}

def prepare_loras(directory, params):
    for target in ('acoustic','planner'):
        name = params.get(target+'_lora')
        if name:
            path = resolve_lora(directory, name)
            try:
                targets = inspect_lora(path)
            except (ValueError, OSError, TypeError) as error:
                raise HTTPException(400, str(error)) from error
            if target not in targets:
                raise HTTPException(400, f'{name} 不含 {target} 类型的 LoRA')
            params[target+'_lora_path'] = str(path)
    return params
