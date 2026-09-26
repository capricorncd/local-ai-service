# 文字转语音与音色转换

两个服务均在 APP 内隔离运行，启动时只检查配置；推理进入统一串行队列，任务完成后释放模型。所有下列接口需要 `Authorization: Bearer <API_KEY>`。默认等待结果，`?wait=false` 返回 202 和任务 ID，使用 `GET /v1/jobs/{id}` 查询；结果中的 `files[].url` 可下载 WAV，仍需认证。异步结果在 `result.files`。

## 预设音色

`GET /v1/voices` 返回音色 ID、中文名称、特点、主要语言、试听 `preview_url` 和是否具备转换参考 `vc_available`。试听：`GET /v1/voices/{id}/audio`。

| ID | 名称 | 特点 |
| --- | --- | --- |
| vivian | 薇薇安 | 明亮年轻女声，中文 |
| serena | 瑟琳娜 | 温柔温暖女声，中文 |
| uncle_fu | 福叔 | 低沉醇厚男声，中文 |
| dylan | 迪伦 | 清亮年轻男声，北京话 |
| eric | 埃里克 | 活泼男声，四川话 |
| ryan | 瑞恩 | 有节奏的动感男声，英文 |
| aiden | 艾登 | 清晰沉稳男声，英文 |
| ono_anna | 小野杏 | 轻快灵动女声，日文 |
| sohee | 素熙 | 温暖有情感的女声，韩文 |

文字转语音直接使用 Qwen3-TTS 内置音色。音色转换使用本 APP 通过同一模型生成的参考录音，存于 `runtimes/voices`，可独立配置目录。转换预设是参考音频，不是训练过的独立 Seed-VC 音色模型。缺少参考时该预设转换不可用，但可以上传自己的参考；生成参考的脚本不会覆盖已有文件。

## 文字转语音

`POST /v1/tts/generate`

```json
{
  "text": "你好，欢迎使用本地语音服务。",
  "speaker": "serena",
  "language": "Chinese",
  "instruct": "用温柔自然的语气说",
  "seed": 42
}
```

- `text` 必填，1–2000 字符，不允许纯空白。
- `speaker` 可选，默认 `vivian`（可在服务配置中改）；预设音色表中的 ID。
- `language` 默认 `Chinese`，支持 `Auto`、`Chinese`、`English`、`Japanese`、`Korean`、`German`、`French`、`Russian`、`Portuguese`、`Spanish`、`Italian`。
- `instruct` 可选，最多 1000 字符，控制预设音色的表达方式；仅 1.7B CustomVoice 模式支持。
- `temperature` 默认 0.9，范围 0.1–2；`max_new_tokens` 默认 2048，范围 128–4096。长文字建议分段；达到生成上限可能截断语音。
- `seed` 默认 42，0–4294967295。同一设备和环境用于复现采样，不保证跨硬件逐样本相同。
- 输出 24 kHz 单声道 PCM16 WAV。默认任务超时 1800 秒。

**参考音色克隆：** 先用 `POST /v1/uploads` 的 multipart `file` 上传清晰的 3–30 秒参考音频或视频，再提交：

```json
{
  "text": "这是需要用参考声音朗读的新文字。",
  "language": "Chinese",
  "reference_upload_id": "上传接口返回的ID",
  "reference_text": "参考录音中实际说出的原文"
}
```

`reference_text` 可选，最多 4000 字符。有准确原文时使用上下文克隆；留空时只提取音色特征，不做自动语音识别。参考模式使用独立的 Base 模型，不可同时指定 `speaker` 或 `instruct`。参考视频取第一条音轨，超时长报错，不静默截断。

独立配置：`tts.python`、`model_dir`（CustomVoice）、`clone_model_dir`（Base）、`ffmpeg`、`output_dir`、`device`、默认音色、语言、采样温度、Token 上限、任务超时。保存后 `POST /v1/services/tts/restart` 生效。默认目录为 `runtimes/models/Qwen3-TTS-12Hz-1.7B-CustomVoice` 和 `runtimes/models/Qwen3-TTS-12Hz-1.7B-Base`，包含各自的 `speech_tokenizer`。

## 音色转换

`POST /v1/voice/convert`，先将原音频或视频上传至 `/v1/uploads`。

使用预设：

```json
{
  "source_upload_id": "原音频上传ID",
  "target_voice": "uncle_fu",
  "diffusion_steps": 30,
  "inference_cfg_rate": 0.7,
  "length_adjust": 1.0,
  "seed": 42
}
```

使用自己的目标声音：将 `target_voice` 替换为 `reference_upload_id`，指向另一次上传的 3–25 秒参考录音。两项必须且只能选一项。建议参考清晰、单人、无伴奏。源音频最短 0.5 秒，默认最长 300 秒；视频取第一条音轨，输出纯音频。

- `diffusion_steps` 默认 30，1–200。
- `inference_cfg_rate` 默认 0.7，0–1，为模型原生引导参数。
- `length_adjust` 默认 1.0，0.5–2，控制相对时长；大于 1 倾向更长、更慢。
- `seed` 默认 42，0–4294967295。
- 输出 22.05 kHz 单声道 PCM16 WAV。当前接入 Seed-VC 的说话声转换模型，不包含实时变声或歌唱基频控制；音色、韵律和转换质量取决于源音频和参考。

独立配置：`vc.python`、`runtime_dir`、`model_dir`、`voices_dir`、`ffmpeg`、`output_dir`、`device`、上述采样默认值、`max_duration`（1–1800 秒）、任务超时（默认 1800 秒）。保存后 `POST /v1/services/vc/restart`。模型目录必须包含主模型、Whisper-small、CAMPPlus 和 BigVGAN；所有组件均从本地加载，推理不下载文件。

## 重建环境

先使用主文档的基础环境脚本准备 APP 内 Python 和 FFmpeg，然后运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup-voice.ps1 -DownloadModels -PrepareVoices
```

`tts`、`vc` 各自独立虚拟环境和锁定依赖，使用 APP 内 Python 3.12 与 CUDA PyTorch。Seed-VC 运行代码固定到 `51383efd921027683c89e5348211d93ff12ac2a8`；本 APP 适配本地组件路径和 PCM WAV 输出，不依赖系统 TorchCodec、FlashAttention 或 CUDA 编译器。准备预设参考需要 NVIDIA GPU；生成后作为普通 WAV 文件使用。

来源：[Qwen3-TTS 官方项目](https://github.com/QwenLM/Qwen3-TTS)、[Seed-VC 官方项目](https://github.com/Plachtaa/seed-vc)。相关许可随各运行代码和模型提供。

## 验证记录

- 自动测试共 21 项通过，新增覆盖配置迁移、认证、音色列表及试听、两种模式参数互斥、上传路径校验、模型缺失与服务独立性。
- `scripts/smoke_voice.py` 在本机 RTX 4090 上实际通过预设 TTS、无参考原文的克隆 TTS、预设 VC、上传参考 VC 四条完整接口路径，均验证成功状态与音频下载。
- 9 个预设参考已生成，长度约 9–12 秒；TTS 返回 24 kHz WAV，VC 返回 22.05 kHz WAV。验证功能与音频格式，不代表跨语种或长语音的主观质量评测。
