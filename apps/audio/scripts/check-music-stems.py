from pathlib import Path
import sys,torch
sys.path.insert(0,str(Path('server').resolve()))
from music_stems import separate_chunks
from torchaudio.models import hdemucs_high
torch.set_num_threads(2)
path=Path('runtimes/models/HDemucs/hdemucs_high_trained.pt')
model=hdemucs_high(sources=['drums','bass','other','vocals'])
model.load_state_dict(torch.load(str(path),map_location='cpu',weights_only=True));model.eval()
rate=44100
t=torch.arange(rate)/rate
wave=(.05*torch.sin(2*torch.pi*440*t)).repeat(2,1)
stems=separate_chunks(model,wave,rate,'cpu',seconds=1,overlap=.1)
assert stems.shape==(4,2,rate) and torch.isfinite(stems).all()
print('HDemucs real CPU inference passed:',tuple(stems.shape))
class Identity:
 sources=['vocals','other']
 def __call__(self,x):return torch.stack([x*.25,x*.75],dim=1)
x=torch.randn(2,253)
y=separate_chunks(Identity(),x,100,'cpu',seconds=1,overlap=.2)
assert torch.allclose(y.sum(0),x,atol=1e-6)
print('Overlapping chunk reconstruction and tail length passed')
