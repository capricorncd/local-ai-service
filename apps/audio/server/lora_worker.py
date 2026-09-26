"""Strict native ComfyUI LoRA application inside the music worker only."""
def apply_music_loras(model, clip, request):
    import torch
    import comfy.lora
    from safetensors.torch import load_file
    reports, cache = [], {}
    for target, prefix in (('acoustic','diffusion_model.'),('planner','text_encoders.')):
        path = request.get(target+'_lora_path')
        if not path:
            continue
        strength = request[target+'_strength']
        if path not in cache:
            cache[path] = load_file(path, device='cpu')
        weights = {k:v for k,v in cache[path].items() if k.startswith(prefix)}
        root = model.model if target == 'acoustic' else clip.cond_stage_model
        mapping = (comfy.lora.model_lora_keys_unet if target=='acoustic' else comfy.lora.model_lora_keys_clip)(root, {})
        state = root.state_dict()
        pairs = [key[:-len('.lora_up.weight')] for key in weights if key.endswith('.lora_up.weight')]
        if not pairs:
            raise ValueError(f'{target}: LoRA 没有可加载的权重')
        for key in pairs:
            weight_key = mapping.get(key)
            if not isinstance(weight_key, str) or weight_key not in state:
                raise ValueError(f'LoRA 与当前 YuE2 模型不匹配: {key}')
            up, down = weights[key+'.lora_up.weight'], weights.get(key+'.lora_down.weight')
            if down is None or up.ndim != 2 or down.ndim != 2 or up.shape[1] != down.shape[0] or tuple(state[weight_key].shape) != (up.shape[0],down.shape[1]):
                raise ValueError(f'LoRA 权重形状与当前模型不匹配: {key}')
        if any(not torch.isfinite(value).all() for value in weights.values()):
            raise ValueError('LoRA 含有无效数值')
        patches = comfy.lora.load_lora(weights, mapping)
        if len(patches) != len(pairs):
            raise ValueError('LoRA 未能完整匹配到模型层')
        if strength:
            if target == 'acoustic':
                model = model.clone()
                applied = model.add_patches(patches, strength)
            else:
                clip = clip.clone()
                applied = clip.add_patches(patches, strength)
            if len(applied) != len(patches):
                raise ValueError('LoRA 部分权重未能加载')
        reports.append({'target':target, 'file':request[target+'_lora'], 'strength':strength,
            'matched_layers':len(patches), 'applied':bool(strength)})
    return model, clip, reports
