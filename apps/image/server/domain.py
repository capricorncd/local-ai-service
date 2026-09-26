from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field, model_validator
import json
import struct

ROOT = Path(__file__).resolve().parents[3]
MODES = ('text', 'continue', 'transparent', 'extract', 'panorama', 'fidelity', 'brush', 'circle', 'mask', 'alpha', 'multi')
MODEL_NAMES = {
    'model': 'qwen_image_2.1_bf16.safetensors',
    'vae': 'qwen_image_2.1_vae_bf16.safetensors',
    'encoder': 'qwen3vl_8b_bf16.safetensors',
}

class Config(BaseModel):
    model_dir: str = ''
    model: str = MODEL_NAMES['model']
    vae: str = MODEL_NAMES['vae']
    encoder: str = MODEL_NAMES['encoder']
    python: str = str(ROOT / 'runtimes/image/Scripts/python.exe')
    core: str = str(ROOT / 'runtimes/image-core')

    def paths(self):
        return {key: Path(self.model_dir) / getattr(self, key) for key in MODEL_NAMES}

def inspect_models(config):
    result = []
    for role, path in config.paths().items():
        error = None
        try:
            if not str(getattr(config, role)).strip() or (not config.model_dir.strip() and not Path(getattr(config, role)).is_absolute()):
                raise ValueError('Please select a model directory or an absolute model file path in Settings')
            with path.open('rb') as f:
                size = struct.unpack('<Q', f.read(8))[0]
                if not 2 <= size <= 32 * 1024 * 1024:
                    raise ValueError('Invalid safetensors header')
                header = json.loads(f.read(size))
                tensors = [v for k, v in header.items() if k != '__metadata__']
                if not tensors or max(v['data_offsets'][1] for v in tensors) + size + 8 != path.stat().st_size:
                    raise ValueError('Incomplete safetensors file')
        except (OSError, ValueError, KeyError, TypeError, struct.error) as e:
            error = str(e)
        result.append({'role': role, 'path': str(path), 'ready': error is None, 'error': error})
    return result

class Generate(BaseModel):
    mode: Literal['text','continue','transparent','extract','panorama','fidelity','brush','circle','mask','alpha','multi'] = 'text'
    prompt: str = Field(min_length=1, max_length=12000)
    negative: str = Field(default='', max_length=4000)
    references: list[str] = Field(default_factory=list, max_length=10)
    mask: str | None = None
    width: int = Field(default=1024, ge=256, le=2048, multiple_of=32)
    height: int = Field(default=1024, ge=256, le=2048, multiple_of=32)
    steps: int = Field(default=30, ge=1, le=80)
    cfg: float = Field(default=4, ge=1, le=10)
    seed: int = Field(default=-1, ge=-1, le=2**32-1)

    @model_validator(mode='after')
    def validate_mode(self):
        if not self.prompt.strip():
            raise ValueError('Please enter an instruction')
        if self.mode not in ('text', 'transparent', 'panorama') and not self.references:
            raise ValueError('This operation requires a reference image')
        if self.mode == 'multi' and len(self.references) < 2:
            raise ValueError('Multi-image editing requires at least two images')
        if self.mode in ('brush', 'circle', 'mask') and not self.mask:
            raise ValueError('Select an editing region or upload a mask')
        if self.width * self.height > 2097152:
            raise ValueError('Maximum output area is 2 megapixels')
        return self

def build_prompt(req):
    instructions = {
        'continue': 'Continue editing image 1 according to the instruction. Preserve unmentioned content.',
        'transparent': 'Generate an RGBA image with a genuinely transparent background, not a checkerboard or solid background.',
        'extract': 'Extract the subject from image 1. Preserve its identity and fine edges. Remove the background and output RGBA with transparency.',
        'panorama': 'Create a seamless 360-degree equirectangular panorama, with matching left and right edges.',
        'fidelity': 'Preserve the exact identity, face, product shape, materials, lettering and distinguishing features of the reference subjects.',
        'brush': 'Edit only the white area in the last reference image (mask) on image 1. Preserve all black areas.',
        'circle': 'Edit only the selected white area in the last reference image (mask) on image 1. Preserve all black areas.',
        'mask': 'Use the last reference image as a mask: white means edit; black means preserve image 1.',
        'alpha': 'Edit image 1 while preserving its transparent background. Output RGBA, not a rendered checkerboard.',
        'multi': 'Use the numbered reference images together according to the instruction, preserving the requested subject identities.',
    }
    prefix = instructions.get(req.mode, '')
    return f'{prefix}\n{req.prompt}'.strip()

class Layer(BaseModel):
    id: str = Field(min_length=1, max_length=200)
    name: str = Field(max_length=500)
    source: str = Field(max_length=45_000_000, pattern=r'^data:image/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+$')
    width: int = Field(ge=1, le=20000)
    height: int = Field(ge=1, le=20000)
    x: float = Field(ge=-20000, le=20000)
    y: float = Field(ge=-20000, le=20000)
    scale: float = Field(ge=.01, le=20)
    opacity: float = Field(ge=0, le=1)
    visible: bool
    locked: bool
    reference: bool

class Project(BaseModel):
    format: Literal['local-ai-image'] = 'local-ai-image'
    version: Literal[1] = 1
    name: str = Field(max_length=500)
    width: int = Field(ge=256, le=2048, multiple_of=32)
    height: int = Field(ge=256, le=2048, multiple_of=32)
    layers: list[Layer] = Field(max_length=50)
    active: str | None
    mask: str | None = Field(default=None, max_length=45_000_000, pattern=r'^data:image/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+$')
    prompt: str = Field(max_length=12000)
    negative: str = Field(max_length=4000)
    mode: Literal['text','continue','transparent','extract','panorama','fidelity','brush','circle','mask','alpha','multi']
    steps: int = Field(ge=1, le=80)
    cfg: float = Field(ge=1, le=10)
    seed: int = Field(ge=-1, le=2**32-1)

    @model_validator(mode='after')
    def check(self):
        ids = {l.id for l in self.layers}
        if len(ids) != len(self.layers) or (self.active is not None and self.active not in ids):
            raise ValueError('Invalid layer selection or duplicate layer IDs')
        if self.width * self.height > 2097152 or any(l.width*l.height > 20_000_000 for l in self.layers):
            raise ValueError('Image pixel limit exceeded')
        return self
