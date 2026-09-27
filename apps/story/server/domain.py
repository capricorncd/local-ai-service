import json
import re
import uuid
from typing import Literal
from pydantic import BaseModel, Field, model_validator, ConfigDict


def uid():
    return uuid.uuid4().hex


class Shot(BaseModel):
    id: str = Field(default_factory=uid, min_length=1)
    title: str = ''
    scene: str = ''
    description: str = ''
    duration: float = Field(default=5, gt=0, le=3600, allow_inf_nan=False)
    shot_size: str = '中景'
    angle: str = '平视'
    camera_move: str = '固定'
    lighting: str = ''
    speaker: str = ''
    dialogue: str = ''
    delivery: str = ''
    emotion: str = ''
    sound: str = ''
    subtitle: str = ''
    asset_ids: list[str] = Field(default_factory=list)
    image: str = ''
    images: list[str] = Field(default_factory=list)
    hidden_images: list[str] = Field(default_factory=list)
    disabled: bool = False
    audio: str = ''
    audio_text: str = ''
    audio_duration: float = Field(default=0, ge=0, allow_inf_nan=False)


class Episode(BaseModel):
    id: str = Field(default_factory=uid)
    title: str = '第1话'
    kind: Literal['episode', 'special'] = 'episode'
    script: str = ''
    shots: list[Shot] = Field(default_factory=list)


class Chapter(BaseModel):
    id: str = Field(default_factory=uid)
    title: str = '第一季'
    episodes: list[Episode] = Field(default_factory=list)


class Asset(BaseModel):
    id: str = Field(default_factory=uid)
    name: str = Field(min_length=1, max_length=200)
    kind: Literal['character', 'scene', 'prop', 'other'] = 'character'
    rating: int = Field(default=0, ge=0, le=5, strict=True)
    deprecated: bool = False
    tags: list[str] = Field(default_factory=list)
    description: str = ''
    gender: str = ''
    body: str = ''
    form: str = ''
    clothing: str = ''
    constraints: str = ''
    image: str = ''
    voice: str = ''
    voice_description: str = ''
    voice_preset: str = 'vivian'
    voice_reference_text: str = ''
    generation_prompt: str = ''


class Project(BaseModel):
    model_config = ConfigDict(extra='forbid')
    format: Literal['local-ai-story'] = 'local-ai-story'
    version: Literal[1] = 1
    id: str = Field(default_factory=uid)
    name: str = Field(min_length=1, max_length=200)
    revision: int = 0
    updated: str = ''
    width: int = Field(default=1376, ge=256, le=2048, multiple_of=32)
    height: int = Field(default=768, ge=256, le=2048, multiple_of=32)
    fps: int = Field(default=24, ge=1, le=120)
    style: str = ''
    chapters: list[Chapter] = Field(default_factory=list)
    assets: list[Asset] = Field(default_factory=list)

    @model_validator(mode='after')
    def check(self):
        if self.width * self.height > 2097152:
            raise ValueError('画面面积不能超过 2,097,152 像素')
        ids = [self.id] + [a.id for a in self.assets]
        assets = {a.id for a in self.assets}
        for c in self.chapters:
            ids.append(c.id)
            for e in c.episodes:
                ids.append(e.id)
                for s in e.shots:
                    ids.append(s.id)
                    if not set(s.asset_ids) <= assets:
                        raise ValueError('分镜引用了不存在的资产')
        if len(ids) != len(set(ids)):
            raise ValueError('项目内 ID 必须唯一')
        for p in [v for a in self.assets for v in (a.image, a.voice)] + [v for c in self.chapters for e in c.episodes for s in e.shots for v in (s.image, s.audio)]:
            if p and not re.fullmatch(r'media/[a-f0-9]{32}\.(png|jpg|jpeg|webp|wav|mp3|ogg|flac|m4a)', p):
                raise ValueError('素材路径必须指向项目 media 目录中的已导入文件')
        return self


class Settings(BaseModel):
    project_directory: str = ''
    provider: Literal['ollama', 'openai'] = 'ollama'
    agent_url: str = 'http://127.0.0.1:11434'
    model: str = 'qwen3:8b'
    api_key: str = ''
    image_url: str = 'http://127.0.0.1:19877'
    image_token: str = ''
    storyboard_max_edge: int = Field(default=1024, ge=256, le=2048, multiple_of=32)
    steps: int = Field(default=30, ge=1, le=80)
    cfg: float = Field(default=4, ge=1, le=10)
    audio_url: str = 'http://127.0.0.1:19876'
    audio_token: str = ''
    tts_model: Literal['qwen3-tts','breeze-tts2'] = 'qwen3-tts'
    tts_speaker: str = 'vivian'
    tts_language: str = 'Chinese'


def import_script(text, filename='导入剧本'):
    """Split only explicit structural headings; preserve all original body lines."""
    chapters, current, episode = [], None, None
    for line in text.replace('\r\n', '\n').split('\n'):
        heading = re.sub(r'^#{1,6}\s*', '', line).strip().strip('【】')
        if re.match(r'^第[\d一二三四五六七八九十百零〇]+[季章卷部]', heading):
            current = Chapter(title=heading)
            chapters.append(current)
            episode = None
        elif re.match(r'^(第[\d一二三四五六七八九十百零〇]+[话話集]|特别篇|番外)', heading):
            if current is None:
                current = Chapter(); chapters.append(current)
            episode = Episode(title=heading, kind='special' if heading.startswith(('特别篇', '番外')) else 'episode')
            current.episodes.append(episode)
        else:
            if not line.strip() and episode is None:
                continue
            if current is None:
                current = Chapter(); chapters.append(current)
            if episode is None:
                episode = Episode(title=filename); current.episodes.append(episode)
            episode.script += line + '\n'
    return chapters


def parse_agent_shots(text, assets):
    text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text.strip())
    obj = json.loads(text)
    if not isinstance(obj, dict) or not isinstance(obj.get('shots'), list) or not obj['shots']:
        raise ValueError('Agent 必须返回包含非空 shots 数组的 JSON 对象')
    allowed = {a.id for a in assets}
    result = []
    for raw in obj['shots']:
        s = Shot.model_validate(raw)
        if not set(s.asset_ids) <= allowed:
            raise ValueError('Agent 返回了未知资产引用，请重新生成')
        # New proposals cannot invent files or collide with persisted shot IDs.
        s.id, s.image, s.audio, s.audio_text, s.audio_duration = uid(), '', '', '', 0
        s.images, s.hidden_images = [], []
        result.append(s)
    return result


def storyboard_image_size(width: int, height: int, max_edge: int):
    scale = min(1, max_edge / max(width, height))
    # The image service accepts multiples of 32 and a minimum side of 256.
    return tuple(min(max_edge, max(256, int(side * scale / 32 + .5) * 32)) for side in (width, height))
