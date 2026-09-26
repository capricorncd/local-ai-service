"""Check native LoRA application against actual YuE2 weights; synthetic test adapters, not trained LoRAs."""
import sys
import argparse
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--checkpoint', required=True, type=Path, help='Path to the YuE2 safetensors model')
args=parser.parse_args()
checkpoint=args.checkpoint.expanduser().resolve()
if not checkpoint.is_file():
    parser.error('The checkpoint file does not exist')
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'server'))
sys.path.insert(0,str(ROOT/'runtimes/ComfyUI'))
sys.argv=[sys.argv[0],'--disable-all-custom-nodes']
import comfy.options
comfy.options.enable_args_parsing()
import torch
import comfy.sd
import comfy.lora
from safetensors.torch import save_file
from lora_worker import apply_music_loras

directory=ROOT/'data/smoke-lora'; directory.mkdir(exist_ok=True)
model,clip,_=comfy.sd.load_checkpoint_guess_config(str(checkpoint),output_vae=False,output_clip=True)[:3]
selected=[]
for target,root,prefix in [('acoustic',model.model,'diffusion_model.'),('planner',clip.cond_stage_model,'text_encoders.')]:
    state=root.state_dict()
    key=next(k for k,v in state.items() if k.endswith('self_attn.o_proj.weight') and v.ndim==2)
    base=key[:-len('.weight')]
    name=base if target=='acoustic' else prefix+base
    out_dim,in_dim=state[key].shape
    save_file({name+'.lora_up.weight':torch.full((out_dim,1),.01),name+'.lora_down.weight':torch.full((1,in_dim),.01),name+'.alpha':torch.tensor(1.)},str(directory/(target+'.safetensors')))
    selected.append((target,key))
request={'lora_provider':'speedyrulz','acoustic_lora':'acoustic.safetensors','planner_lora':'planner.safetensors',
    'acoustic_lora_path':str(directory/'acoustic.safetensors'),'planner_lora_path':str(directory/'planner.safetensors'),
    'acoustic_strength':.5,'planner_strength':.7}
patched_model,patched_clip,reports=apply_music_loras(model,clip,request)
for target,key in selected:
    patcher=patched_model if target=='acoustic' else patched_clip.patcher
    patches=patcher.patches[key]
    shape=patcher.model.state_dict()[key].shape
    delta=comfy.lora.calculate_weight(patches,torch.zeros(shape),key)
    expected=.0001*request[target+'_strength']
    assert torch.allclose(delta,torch.full_like(delta,expected),atol=1e-7),target
    print('PASS actual YuE2 patch:',target,key,flush=True)
assert not model.patches and not clip.patcher.patches
print(reports,flush=True)
request['acoustic_strength']=0;request['planner_strength']=0
m,c,report=apply_music_loras(model,clip,request)
assert m is model and c is clip and all(not r['applied'] for r in report)
print('PASS zero strength leaves base model unchanged',flush=True)
