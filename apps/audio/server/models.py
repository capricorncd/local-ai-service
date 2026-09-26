from pathlib import Path
from typing import Literal
import sys
import os
from pydantic import BaseModel, Field, ConfigDict, model_validator

ROOT = Path(os.environ.get('LOCAL_AI_ROOT', str(Path(__file__).resolve().parents[1])))
INSTRUMENTAL_STYLE = 'Instrumental only, no vocals, no singing, no spoken words, no humming, no choir'

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')

class MusicConfig(StrictModel):
    stems_model_path: str = str(ROOT / 'runtimes/models/HDemucs/hdemucs_high_trained.pt')
    ffmpeg: str = str(ROOT / 'runtimes/ffmpeg/bin/ffmpeg.exe')
    enabled: bool = True
    python: str = str(ROOT / 'runtimes/music/Scripts/python.exe')
    runtime_dir: str = str(ROOT / 'runtimes' / 'ComfyUI')
    model_path: str = ''
    encoder_path: str = ''
    output_dir: str = ''
    lora_dir: str = str(ROOT / 'runtimes/models/YuE2-LoRA')
    device: Literal['cuda', 'cpu'] = 'cuda'
    default_count: int = Field(1, ge=1, le=2)
    steps: int = Field(32, ge=1, le=100)
    cfg: float = Field(1.0, ge=0, le=20)
    max_duration: float = Field(360, ge=1, le=900)
    timeout_seconds: int = Field(3600, ge=30, le=14400)

class DenoiseConfig(StrictModel):
    enabled: bool = True
    python: str = str(ROOT / 'runtimes/denoise/Scripts/python.exe')
    model_dir: str = str(ROOT / 'runtimes/models/MossFormer2_SE_48K')
    output_dir: str = ''
    ffmpeg: str = str(ROOT / 'runtimes/ffmpeg/bin/ffmpeg.exe')
    device: Literal['cuda', 'cpu'] = 'cuda'
    segment_seconds: float = Field(20, ge=4, le=120)
    max_duration: int = Field(1800, ge=1, le=7200)
    timeout_seconds: int = Field(1800, ge=30, le=14400)

class LibraryConfig(StrictModel):
    enabled: bool = True
    directory: str = ''
    database: str = ''

class SeparationConfig(DenoiseConfig):
    model_dir: str = str(ROOT / 'runtimes/models/MossFormer2_SS_16K')
    segment_seconds: float = Field(2, ge=2, le=120)

class SfxConfig(StrictModel):
    enabled: bool = True
    python: str = str(ROOT / 'runtimes/sfx/Scripts/python.exe')
    model_dir: str = str(ROOT / 'runtimes/models/MOSS-SoundEffect-v2.0')
    output_dir: str = ''
    device: Literal['cuda', 'cpu'] = 'cuda'
    seconds: float = Field(10, ge=1, le=30)
    num_inference_steps: int = Field(100, ge=1, le=200)
    cfg_scale: float = Field(4, ge=1, le=20)
    sigma_shift: float = Field(5, gt=0, le=20)
    default_count: int = Field(1, ge=1, le=4)
    timeout_seconds: int = Field(1800, ge=30, le=14400)

Language = Literal['Auto','Chinese','English','Japanese','Korean','German','French','Russian','Portuguese','Spanish','Italian']
Speaker = Literal['vivian','serena','uncle_fu','dylan','eric','ryan','aiden','ono_anna','sohee']

class TtsConfig(StrictModel):
    breeze_runtime_dir: str = str(ROOT / 'runtimes/breeze-tts')
    breeze_model_dir: str = str(ROOT / 'runtimes/models/Breeze-TTS-2')
    breeze_output_dir: str = str(ROOT / 'data/breeze-output')
    breeze_cfg_scale: float = Field(4, gt=0, le=20)
    breeze_fast: bool = False
    enabled: bool = True
    python: str = str(ROOT / 'runtimes/tts/Scripts/python.exe')
    model_dir: str = str(ROOT / 'runtimes/models/Qwen3-TTS-12Hz-1.7B-CustomVoice')
    clone_model_dir: str = str(ROOT / 'runtimes/models/Qwen3-TTS-12Hz-1.7B-Base')
    output_dir: str = ''
    ffmpeg: str = str(ROOT / 'runtimes/ffmpeg/bin/ffmpeg.exe')
    device: Literal['cuda','cpu'] = 'cuda'
    speaker: Speaker = 'vivian'
    language: Language = 'Chinese'
    temperature: float = Field(.9, ge=.1, le=2)
    max_new_tokens: int = Field(2048, ge=128, le=4096)
    timeout_seconds: int = Field(1800, ge=30, le=14400)

class VcConfig(StrictModel):
    enabled: bool = True
    python: str = str(ROOT / 'runtimes/vc/Scripts/python.exe')
    runtime_dir: str = str(ROOT / 'runtimes/Seed-VC')
    model_dir: str = str(ROOT / 'runtimes/models/Seed-VC')
    voices_dir: str = str(ROOT / 'runtimes/voices')
    output_dir: str = ''
    ffmpeg: str = str(ROOT / 'runtimes/ffmpeg/bin/ffmpeg.exe')
    device: Literal['cuda','cpu'] = 'cuda'
    diffusion_steps: int = Field(30, ge=1, le=200)
    inference_cfg_rate: float = Field(.7, ge=0, le=1)
    length_adjust: float = Field(1, ge=.5, le=2)
    max_duration: int = Field(300, ge=1, le=1800)
    timeout_seconds: int = Field(1800, ge=30, le=14400)

class AukConfig(StrictModel):
    enabled: bool = True
    python: str = str(ROOT / 'runtimes/auk-env/Scripts/python.exe')
    model_dir: str = str(ROOT / 'runtimes/models/AuK')
    qwen_dir: str = str(ROOT / 'runtimes/models/Qwen2.5-Omni-3B')
    output_dir: str = ''
    ffmpeg: str = str(ROOT / 'runtimes/ffmpeg/bin/ffmpeg.exe')
    device: Literal['cuda', 'cpu'] = 'cuda'
    cpu_offload: bool = True
    steps: int = Field(32, ge=1, le=100)
    cfg: float = Field(2, ge=0, le=10)
    timeout_seconds: int = Field(1800, ge=30, le=14400)


class AukRequest(StrictModel):
    task: Literal['content','lyrics','pitch','speed','volume','emotion','timbre','accent','nonverbal','whisper','enhance','separate','vocals','speaker','tts','clone','custom'] = 'custom'
    instruction: str = Field(min_length=1, max_length=4000)
    upload_id: str | None = None
    clip_start: float = Field(0, ge=0, le=7200)
    clip_seconds: float = Field(10, gt=0, le=29)
    gen_seconds: float = Field(10, gt=0, le=30)
    seed: int = Field(42, ge=0, le=2**32-1)
    steps: int | None = Field(None, ge=1, le=100)
    cfg: float | None = Field(None, ge=0, le=10)

    @model_validator(mode='after')
    def valid_audio(self):
        if not self.instruction.strip():
            raise ValueError('请输入操作指令')
        if self.task not in ('tts','custom') and not self.upload_id:
            raise ValueError('此操作需要上传音频')
        if self.upload_id and self.clip_seconds + self.gen_seconds > 30:
            raise ValueError('输入片段与输出时长合计不得超过 30 秒')
        return self


class Config(StrictModel):
    auk: AukConfig = Field(default_factory=AukConfig)
    tts: TtsConfig = Field(default_factory=TtsConfig)
    vc: VcConfig = Field(default_factory=VcConfig)
    sfx: SfxConfig = Field(default_factory=SfxConfig)
    music: MusicConfig = Field(default_factory=MusicConfig)
    denoise: DenoiseConfig = Field(default_factory=DenoiseConfig)
    separation: SeparationConfig = Field(default_factory=SeparationConfig)
    library: LibraryConfig = Field(default_factory=LibraryConfig)

class MusicWorkspaceRequest(StrictModel):
    name: str = Field(min_length=1, max_length=60)

class MusicAnnotationRequest(StrictModel):
    rating: int = Field(ge=0, le=5, strict=True)
    favorite: bool = Field(strict=True)

class MusicRequest(StrictModel):
    workspace: str = Field('', max_length=60)
    title: str = Field('', max_length=120)
    generate_score: bool = False
    lora_provider: Literal['none', 'speedyrulz', 'starnodes2024'] = 'none'
    acoustic_lora: str | None = None
    planner_lora: str | None = None
    acoustic_strength: float = Field(1, ge=0, le=3)
    planner_strength: float = Field(1, ge=0, le=3)
    lyrics: str = Field('', max_length=20000)
    style: str = Field('', max_length=4000)
    vocal_gender: Literal['default', 'male', 'female'] = 'default'
    count: int | None = Field(None, ge=1, le=2)
    seed: int = Field(42, ge=0, le=2**32-2)
    steps: int | None = Field(None, ge=1, le=100)
    cfg: float | None = Field(None, ge=0, le=20)
    max_duration: float | None = Field(None, ge=1, le=900)
    mode: Literal['full', 'melody', 'off'] = 'full'
    temperature: float = Field(1, ge=0.01, le=5)
    top_p: float = Field(0.95, ge=0.01, le=1)
    top_k: int = Field(100, ge=1, le=32768)
    repetition_penalty: float = Field(1.2, ge=0.01, le=10)

    @model_validator(mode='after')
    def lora_options(self):
        self.workspace = self.workspace.strip()
        self.style = self.style.strip()
        self.lyrics = self.lyrics.strip() or '[Instrumental]'
        if self.lyrics.lower() == '[instrumental]' and INSTRUMENTAL_STYLE not in self.style:
            self.style = ', '.join(filter(None, [self.style, INSTRUMENTAL_STYLE]))
            if len(self.style) > 4000:
                raise ValueError('纯音乐提示词过长，请缩短音乐风格描述')
        if self.generate_score and self.mode == 'off':
            raise ValueError('生成曲谱需要 full 或 melody 乐谱规划模式')
        if self.lora_provider == 'none' and (self.acoustic_lora or self.planner_lora):
            raise ValueError('选择 LoRA 文件前请指定 lora_provider')
        if self.lora_provider != 'none' and not (self.acoustic_lora or self.planner_lora):
            raise ValueError('请选择至少一个 LoRA 文件')
        if self.lora_provider == 'starnodes2024' and self.planner_lora:
            raise ValueError('Starnodes2024 方案仅支持声学 LoRA')
        return self

class DenoiseRequest(StrictModel):
    upload_id: str
    segment_seconds: float | None = Field(None, ge=4, le=120)
    max_duration: int | None = Field(None, ge=1, le=7200)

class SeparationRequest(DenoiseRequest):
    mode: Literal['speakers', 'music', 'both'] = 'speakers'
    title: str = Field('', max_length=120)
    segment_seconds: float | None = Field(None, ge=2, le=120)

class SfxRequest(StrictModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    prompt: str = Field(min_length=1, max_length=4000)
    negative_prompt: str = Field('', max_length=4000)
    seconds: float | None = Field(None, ge=1, le=30)
    num_inference_steps: int | None = Field(None, ge=1, le=200)
    cfg_scale: float | None = Field(None, ge=1, le=20)
    sigma_shift: float | None = Field(None, gt=0, le=20)
    count: int | None = Field(None, ge=1, le=4)
    seed: int = Field(42, ge=0, le=2**32-4)

class TtsRequest(StrictModel):
    model: Literal['qwen3-tts', 'breeze-tts2'] = 'qwen3-tts'
    cfg_scale: float | None = Field(None, gt=0, le=20)
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    text: str = Field(min_length=1, max_length=2000)
    speaker: Speaker | None = None
    language: Language | None = None
    reference_upload_id: str | None = None
    reference_text: str = Field('', max_length=4000)
    instruct: str = Field('', max_length=1000)
    temperature: float | None = Field(None, ge=.1, le=2)
    max_new_tokens: int | None = Field(None, ge=128, le=4096)
    seed: int = Field(42, ge=0, le=2**32-1)

    @model_validator(mode='after')
    def compatible_options(self):
        if self.model == 'breeze-tts2':
            if self.speaker:
                raise ValueError('Breeze 不支持 Qwen 预设 speaker，请使用 instruct 设计音色或上传参考音频')
            if self.language not in (None, 'Auto', 'Chinese', 'English'):
                raise ValueError('Breeze 仅支持 Chinese、English、Auto')
            if self.reference_upload_id and not self.reference_text:
                raise ValueError('Breeze 克隆需要 reference_text 准确原文')
            if not self.reference_upload_id and not self.instruct:
                raise ValueError('Breeze 音色设计需要 instruct')
            if self.temperature is not None or self.max_new_tokens is not None:
                raise ValueError('Breeze 暂不支持 temperature 或 max_new_tokens，请使用 cfg_scale')
        elif self.cfg_scale is not None:
            raise ValueError('cfg_scale 仅用于 Breeze')
        if self.reference_upload_id and (self.speaker or (self.instruct and self.model == 'qwen3-tts')):
            raise ValueError('参考音色模式不能同时指定预设 speaker 或 instruct')
        if self.reference_text and not self.reference_upload_id:
            raise ValueError('reference_text 需要 reference_upload_id')
        return self

class VcRequest(StrictModel):
    source_upload_id: str
    reference_upload_id: str | None = None
    target_voice: Speaker | None = None
    diffusion_steps: int | None = Field(None, ge=1, le=200)
    inference_cfg_rate: float | None = Field(None, ge=0, le=1)
    length_adjust: float | None = Field(None, ge=.5, le=2)
    seed: int = Field(42, ge=0, le=2**32-1)

    @model_validator(mode='after')
    def one_target(self):
        if bool(self.reference_upload_id) == bool(self.target_voice):
            raise ValueError('请在 reference_upload_id 和 target_voice 中选择且仅选择一项')
        return self


class ScoreEditRequest(StrictModel):
    workspace: str = Field('', max_length=60)
    job_id: str
    score_index: int = Field(ge=0)
    abc: str = Field(min_length=1, max_length=100000)

    @model_validator(mode='after')
    def valid_score(self):
        if not self.abc.strip() or not any(line.startswith('K:') for line in self.abc.splitlines()):
            raise ValueError('ABC 曲谱不能为空，且必须包含 K: 调号字段')
        return self


class SongMetadata(StrictModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=120)
    group: str = Field('', max_length=60)


class MusicTranscribeRequest(StrictModel):
    upload_id: str = Field(min_length=1)
    workspace: str = Field('', max_length=60)
    title: str = Field('', max_length=120)
    mode: Literal['full', 'melody'] = 'full'


class MusicAudioReferenceRequest(StrictModel):
    upload_id: str
    music: MusicRequest

    @model_validator(mode='after')
    def valid_reference(self):
        if self.music.mode == 'off' or self.music.planner_lora:
            raise ValueError('参考歌曲需要旋律或完整规划模式，且不能使用规划 LoRA')
        return self


class MusicSeparateRequest(StrictModel):
    job_id: str
    audio_index: int = Field(0, ge=0)


class MusicVariationRequest(StrictModel):
    job_id: str
    audio_index: int = Field(ge=0)
    reference: Literal['audio', 'score']
    music: MusicRequest
    abc: str | None = Field(None, min_length=1, max_length=100000)

    @model_validator(mode='after')
    def valid_reference(self):
        if self.music.mode == 'off':
            raise ValueError('参考歌曲需要旋律或完整规划模式')
        if self.music.planner_lora:
            raise ValueError('参考歌曲不使用规划 LoRA，请取消选择')
        if self.abc is not None:
            if self.reference != 'score' or not any(line.startswith('K:') for line in self.abc.splitlines()):
                raise ValueError('编辑曲谱需要曲谱参考模式，且包含 K: 调号')
        return self


class MusicUploadSeparateRequest(StrictModel):
    upload_id: str
    title: str = Field('', max_length=120)
