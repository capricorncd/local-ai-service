"""One managed inference process per job; exiting releases all GPU allocations.

Uses ComfyUI's Python inference core, never its HTTP server or custom nodes.
"""
import json
import sys
from pathlib import Path

def main(payload_path):
    payload = json.loads(Path(payload_path).read_text('utf-8'))
    cfg, req = payload['config'], payload['request']
    output = Path(payload['output'])
    def progress(value):
        tmp = output.with_name('progress.tmp')
        tmp.write_text(json.dumps({'progress': value}))
        tmp.replace(output.with_name('progress.json'))
    sys.path.insert(0, cfg['core'])
    # Comfy's parser must not interpret the worker's input filename as a CLI flag.
    sys.argv = [sys.argv[0]]
    import torch
    import numpy as np
    from PIL import Image
    from PIL.PngImagePlugin import PngInfo
    import comfy.sd
    import comfy.sample
    import comfy.model_management as mm
    import comfy.utils
    import node_helpers

    progress(1)
    paths = {key: str(Path(cfg['model_dir']) / cfg[key]) for key in ('model', 'vae', 'encoder')}
    with torch.inference_mode():
        clip = comfy.sd.load_clip([paths['encoder']], clip_type=comfy.sd.CLIPType.QWEN_IMAGE)
        vae = comfy.sd.VAE(sd=comfy.utils.load_torch_file(paths['vae'], safe_load=True))
        images_vl, ref_latents = [], []
        sources = payload['references'] + ([payload['mask']] if payload['mask'] else [])
        width, height = req['width'], req['height']
        if sources:
            with Image.open(sources[0]) as im:
                ratio = im.width / im.height
            area = width * height
            width = max(32, round((area * ratio)**.5 / 32) * 32)
            height = max(32, round((area / ratio)**.5 / 32) * 32)
        for path in sources:
            with Image.open(path) as im:
                # All edit inputs share the canvas; transparent pixels stay transparent.
                rgba = np.asarray(im.convert('RGBA').resize((width, height), Image.Resampling.LANCZOS)).copy()
            tensor = torch.from_numpy(rgba).float().unsqueeze(0) / 255
            rgb = tensor[..., :3] * tensor[..., 3:] + (1 - tensor[..., 3:])
            images_vl.append(rgb)
            ref_latents.append(vae.encode(tensor))
        progress(10)
        positive = clip.encode_from_tokens_scheduled(clip.tokenize(payload['prompt'], images=images_vl, keep_vision=not ref_latents, prevent_empty_text=True))
        negative = clip.encode_from_tokens_scheduled(clip.tokenize(req['negative'], images=images_vl, keep_vision=not ref_latents, prevent_empty_text=True))
        if ref_latents:
            positive = node_helpers.conditioning_set_values(positive, {'reference_latents': ref_latents}, append=True)
            negative = node_helpers.conditioning_set_values(negative, {'reference_latents': ref_latents}, append=True)
        del clip
        mm.unload_all_models()
        progress(20)
        model = comfy.sd.load_diffusion_model(paths['model'], model_options={'dtype': torch.bfloat16})
        if model is None:
            raise RuntimeError('Qwen Image 2.1 model was not recognized')
        model.model_options.setdefault('transformer_options', {})['qwen_image21_cache'] = {'device':'auto','dtype':'default'}
        latent = torch.zeros([1,64,height//16,width//16], device=mm.intermediate_device())
        noise = comfy.sample.prepare_noise(latent, req['seed'])
        samples = comfy.sample.sample(model, noise, req['steps'], req['cfg'], 'euler', 'simple', positive, negative, latent,
            seed=req['seed'], callback=lambda step,*_: progress(20 + round(70*(step+1)/req['steps'])))
        decoded = vae.decode(samples)[0].float().cpu().numpy()
        image = Image.fromarray(np.clip(decoded * 255,0,255).round().astype(np.uint8))
        if payload['mask']:
            with Image.open(payload['references'][0]) as original, Image.open(payload['mask']) as mask:
                # Exact preservation outside the selected area, at original resolution.
                original = original.convert('RGBA')
                image = Image.composite(image.convert('RGBA').resize(original.size,Image.Resampling.LANCZOS), original, mask.convert('L'))
        metadata = {
            'schema_version':1, 'asset_name':output.parent.name, 'asset_type':'image',
            'generation_prompt':payload['prompt'], 'generation_prompt_status':'exact',
            'generation_prompt_source':'Local AI Image job input', 'generation_mode':'external',
            'reference_images':[{'filename':Path(p).name, 'role':'mask' if p == payload['mask'] else 'reference'} for p in sources],
            'parameters':req, 'model_files':{key:Path(path).name for key,path in paths.items()},
        }
        info = PngInfo()
        info.add_itxt('ImageAssetMetadata', json.dumps(metadata,ensure_ascii=False))
        info.add_itxt('GenerationPrompt', payload['prompt'])
        image.save(output, pnginfo=info)
        with Image.open(output) as verify:
            if json.loads(verify.info['ImageAssetMetadata'])['generation_prompt'] != payload['prompt']:
                raise RuntimeError('Output prompt metadata verification failed')
        progress(100)

if __name__ == '__main__':
    main(sys.argv[1])
