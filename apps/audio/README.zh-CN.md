# Local AI Service

[English](README.md) | 中文文档

音乐生成新增可选 **speedyrulz / Starnodes2024 LoRA**，默认关闭。支持原生 ComfyUI safetensors 文件选择、声学 / 规划权重配置和接口调用，详见 [YuE2 LoRA 使用说明](docs/music-lora.md)。本次提供选择和加载功能，不包含训练。

## 配合 ComfyUI-Capricorncd-Timeline 使用

音乐生成页新增可折叠的“创作预设与风格”：伴奏重编、手动指定原 BPM、完整歌曲构思、参考风格、男/女声、纯音乐 BGM，以及古风、Q版古风、流行、摇滚等 12 种风格按钮。一键填入后可继续编辑，不会自动提交。歌词留空默认纯音乐；有无参考时风格均可留空，不随机补入、不强制继承原曲风格，由模型发挥；空歌词时仅补充无人声提示，也不保证自动匹配原曲风格。BPM、人声和无人声均为提示引导，时长为生成上限，不是真正续接。详见 [预设说明与资料来源](docs/music-presets.md)。

本应用可配合 [ComfyUI-Capricorncd-Timeline](https://github.com/capricorncd/ComfyUI-Capricorncd-Timeline) 使用，实现 **AI 生成视频的音频修复与 BGM 创作**。Timeline 负责分镜生成、剪辑和合成，本应用提供本地音频处理与生成能力。

- **视频音频修复**：将生成视频或其中的音频导入本应用，进行语音降噪，或使用 AuK 编辑其支持的语音片段。替换原音轨前先试听，处理效果取决于原始素材与模型。
- **BGM 创作**：根据场景、情绪、乐器和风格生成背景音乐。需要纯音乐时，可在歌词中填写 `[Instrumental]`，并在风格中明确不要人声。这属于提示词引导，不能保证完全无人声；必要时可使用歌曲人声分离获取伴奏，并检查是否有残留人声。
- **补充音效**：通过 MOSS-SoundEffect 生成环境或动作音效，也可从本地音效库查找已有素材。

推荐流程：在 Timeline 生成视频片段 → 在本应用修复或创作音频 → 下载结果并导入 Timeline 音轨 → 对齐时间、调整音量并合成视频。替换原声时，将对应原音轨静音，避免重复播放。

上述为通过文件导入导出的配合流程。若要直接通过 API 联动，还需按 Timeline 的服务协议适配；本说明不代表已经内置一键直连功能。

## 文字转语音、音色转换与预设音色

新增 Qwen3-TTS 文字转语音与 Seed-VC 音色转换两个独立服务。提供 **9 个可选择、可试听的预设音色**，也支持上传参考音频。页面“文字转语音”“音色转换”可直接操作。

- `GET /v1/voices`：音色列表、中文名称、特点和试听地址。
- `POST /v1/tts/generate`：文字 + 预设音色 / 参考音频 → 语音。
- `POST /v1/voice/convert`：原音频 + 预设音色 / 参考音频 → 转换后的音频。
- [完整请求示例、参数、预设音色表与安装说明](docs/voice-api.md)。

## 音效生成：MOSS-SoundEffect v2.0

`POST /v1/sfx/generate`，使用与其他业务接口相同的 Bearer API Key。默认等待完成；加 `?wait=false` 返回 202 和任务 ID，通过 `/v1/jobs/{id}` 查询结果。

```json
{
  "prompt": "雨水轻轻落在树叶上，远处偶尔传来鸟鸣，没有音乐和说话声。",
  "seconds": 10,
  "count": 1,
  "seed": 42,
  "num_inference_steps": 100,
  "cfg_scale": 4.0,
  "sigma_shift": 5.0,
  "negative_prompt": ""
}
```

| 参数 | 默认值 | 范围与含义 |
| --- | --- | --- |
| `prompt` | 必填 | 中英文音效描述，去除首尾空白后 1–4000 字符 |
| `seconds` | 10 | 1–30 秒，模型按 0.1 秒精度输出 |
| `count` | 1 | 1–4 个，同一任务顺序生成，复用模型 |
| `seed` | 42 | 0–4294967292，各结果使用 seed、seed+1 等 |
| `num_inference_steps` | 100 | 1–200，采样步数；减少可加快采样，可能降低质量 |
| `cfg_scale` | 4 | 1–20，模型原生提示词引导系数 |
| `sigma_shift` | 5 | 大于 0 且不超过 20，模型原生采样调度偏移 |
| `negative_prompt` | 空字符串 | 不希望出现的声音描述，最多 4000 字符 |

省略时长、数量、步数、引导系数或调度偏移时，使用**已重启生效**的 `sfx` 服务配置。默认超时 1800 秒。没有人为混合原音或“强度”参数。输出为 48 kHz 单声道 PCM16 WAV，结果 `files[]` 含 `path`、`url`、`duration`、`sample_rate`、`seed`。下载 `url` 仍需 Bearer 认证。异步返回中这些字段位于 `result.files`，同步成功响应中位于顶层 `files`。

服务自动检查配置，但仅在执行任务时加载模型，与音乐、降噪和人声分离共用串行任务队列。任务结束即退出推理进程并释放模型。输出默认保存在应用数据目录的 `sfx/<任务ID>/`。如需纳入音效库，可将输出目录设为音效库根目录下的子目录，保存后重启 `sfx`，生成后在音效库点击扫描；不会自动复制或扫描其他目录。

独立环境重建（先完成下文基础运行环境准备）：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup-sfx.ps1 -DownloadModel
```

脚本使用 APP 内 Python 3.12、`runtimes/sfx` 与固定依赖清单 `requirements/sfx.lock.txt`。官方运行代码固定到 `934d6826b084c46a0d033402174d5f8ac4ed2519`，仅安装音效子包，不安装整个 MOSS-TTS 环境。Windows 默认禁用 TorchDynamo 编译，使用 PyTorch CUDA 推理，无需系统安装 Triton。推理禁止联网自动下载；缺失文件时显示待配置，配置后手动重启此服务。模型首次下载需要网络。

来源：[官方模型说明](https://huggingface.co/OpenMOSS-Team/MOSS-SoundEffect-v2.0)、[官方运行代码](https://github.com/OpenMOSS/MOSS-TTS/tree/main/moss_soundeffect_v2)。模型卡标注 Apache-2.0。此模型是音效生成模型，与降噪用的 MossFormer2 不同。

验证：`pytest tests -q` 共 16 项通过；`scripts/smoke_sfx.py` 已在本机 RTX 4090 上通过真实模型验证，中文提示词、10 步、两条 3 秒音效均返回可下载的 48 kHz WAV（seed 42/43）。此测试验证功能与文件格式，不代表主观音质评测。

桌面程序实际 HTTP 接口也已使用完整默认参数（10 秒、100 步、1 个结果）生成并下载成功，示例文件在 `data/sfx-default-sample.wav`，任务记录中可直接试听。

Windows 本地 AI 服务管理程序：**Tauri v2 / Rust + React + Lucide**。Rust 管理窗口与进程树；轻量 Python API 提供 HTTP 服务；音乐与语音处理在隔离的 Python 环境中按任务运行，降噪与分离共享本 APP 内的 ClearVoice 环境。模型代码不会导入 API 进程。

## 运行

直接双击根目录的 **`Local-AI-Service.exe`**。请保留旁边的 `server/` 和 `runtimes/`。当前目录已经准备好独立解释器、GPU 运行库、FFmpeg 和 MossFormer2 权重。

- 打开程序后自动启动 `http://127.0.0.1:19876`，分别检查七个服务。
- 音效生成：使用 `MOSS-SoundEffect v2.0`，支持中英文描述，独立配置与隔离运行环境。默认模型目录 `runtimes/models/MOSS-SoundEffect-v2.0`，需完整下载文本编码器、tokenizer、生成模型及 VAE。
- 音效库：进入“音效资源库 → 配置”，选择根目录，保存后点击“重启服务”，再点击“扫描目录”。子文件夹路径自动成为分类。
- 音乐：在音乐服务配置中选择 YuE2 模型文件；使用音频参考或 Cover 转谱时，再选择 SheetSage2 编码器文件。首次使用需自行配置，可复用已有 ComfyUI 模型文件。保存后重启音乐服务。
- 降噪：默认使用本 APP 下的 `runtimes/models/MossFormer2_SE_48K`。
- 人声分离：独立服务，默认使用 `runtimes/models/MossFormer2_SS_16K`。分别配置模型目录、输出目录、设备、时长和超时；保存后单独重启即可。旧配置首次打开时自动补充该服务，不改变原降噪配置。
- API Key 在“API 接入”页查看/复制。仅监听回环地址，所有业务接口使用 Bearer 认证。
- 配置、SQLite、日志和结果默认存于 `%APPDATA%\studio.local-ai.manager`；页面“应用设置”显示实际位置。
- 缺失模型、目录或运行环境时，对应服务显示“待配置”；其他服务继续工作。修改配置不会自动切换正在运行的模型，必须手动重启对应服务。
- 关闭桌面窗口即退出服务。Windows Job Object 会终止 API、推理进程及 FFmpeg 子进程。再次打开时，未完成任务标记为中断失败，不自动重跑。

这是一份包含本地依赖目录的 Windows 开发交付，不是单文件安装包。虚拟环境中有绝对路径；移动整个目录或换电脑后，运行环境需在新路径用下方脚本重建，再在应用设置中更新 API Python 路径，各服务的模型/输出路径也要按需更新。

## GPU 和内存

**程序启动不会加载 AI 模型，也不会为模型占用显存。** API 常驻使用少量 CPU/RAM；WebView 本身可能有图形渲染资源占用。接到推理任务才启动独立进程并加载模型；本 APP 的音乐、音效、文字转语音、音色转换、降噪和人声分离串行执行，队列上限 32。每个任务结束、失败、取消或超时后释放进程与模型资源。

优点是空闲时没有模型显存驻留；代价是每次任务都需要加载权重。生成两首歌曲在同一任务中复用模型，顺序执行并分别使用 seed、seed+1。其他应用的 GPU 使用不会被本程序干预；它们占用较多显存时仍可能导致推理失败。

YuE2 使用 Comfy-Org 合并 checkpoint，内含语言/生成模型与音频 VAE。`encoder_path` 保留用于未来转谱/翻唱扩展；**当前歌词生成不加载 SheetSage2，也尚未提供翻唱 API**。时长参数是生成上限，达到上限可能截断歌曲。MossFormer2 专用于语音增强，输出 48 kHz 单声道 WAV；视频取第一条音轨，超过处理时长上限则报错，不静默截断。

## HTTP API

完整机器可读规范：`GET /openapi.json`。FastAPI 交互文档：`/docs`（Swagger UI 资源需要网络）。下述业务接口均需要 `Authorization: Bearer <API_KEY>`。

| 方法 | 路径 | 功能 |
| --- | --- | --- |
| GET | `/health` | 无需认证的存活检查（不是模型就绪检查） |
| GET | `/v1/status` | 独立服务状态、配置错误、待重启标记、当前任务 |
| GET / PUT | `/v1/config` | 获取 / 保存配置；PUT 保存但不热切换 |
| POST | `/v1/services/{music,denoise,separation,sfx,tts,vc,library}/restart` | 重新检查并应用配置；有未完成任务返回 409 |
| GET | `/v1/voices` | 预设音色列表与试听地址 |
| GET | `/v1/voices/{id}/audio` | 预设音色试听 |
| POST | `/v1/tts/generate` | 文字转语音，支持预设及参考音色 |
| POST | `/v1/voice/convert` | 原音频转换为预设或参考音色 |
| POST | `/v1/sfx/generate` | 中文或英文描述生成音效，返回 WAV 列表 |
| POST | `/v1/music/generate` | JSON 歌词、风格与可选参数，返回歌曲列表 |
| POST | `/v1/uploads` | multipart `file` 上传音频或视频，返回 `upload_id`；最大 512 MB |
| POST | `/v1/denoise` | JSON `{"upload_id":"…"}`，返回降噪音频列表 |
| POST | `/v1/denoise/file` | 直接提交 multipart `file`（音频或视频），无需先上传；可选 segment_seconds、max_duration |
| POST | `/v1/separate` | JSON `{"upload_id":"…"}`，分离两位说话人，返回两条音轨 |
| POST | `/v1/separate/file` | multipart `file` 直接上传音频或视频；可选 segment_seconds、max_duration |
| GET | `/v1/jobs` / `/v1/jobs/{id}` | 最近 200 条 / 指定任务 |
| DELETE | `/v1/jobs/{id}` | 取消排队或运行中的任务 |
| GET | `/v1/jobs/{id}/files/{index}` | 下载生成结果 |
| GET | `/v1/sounds?category=自然&q=雨&limit=50&offset=0` | 分类/名称筛选与分页 |
| GET | `/v1/categories` | 分类与数量 |
| POST | `/v1/sounds/scan` | 原子重建当前根目录索引，不修改音效文件 |
| GET | `/v1/sounds/{id}/audio` | 下载或播放音频，支持 HTTP Range |
| GET | `/v1/logs` | 最近 200 行服务日志 |

生成请求：

```json
{
  "lyrics": "[Verse]\n晚风轻轻经过窗台\n[Chorus]\n把心事写成一首歌",
  "style": "Mandarin, indie pop, acoustic guitar, warm female vocal",
  "count": 2,
  "seed": 42,
  "mode": "full",
  "steps": 32,
  "cfg": 1.0,
  "max_duration": 360
}
```

`count` 省略时使用该服务默认数量（1 或 2）。`mode` 支持 `full` / `melody` / `off`。还支持 temperature、top_p、top_k、repetition_penalty，范围见 OpenAPI。

默认同步等待完成，返回 `{id,status,files:[{url,path,seed,sample_rate,duration}],…}`。长任务推荐 `?wait=false`：立刻返回 HTTP 202 和任务对象，轮询 `/v1/jobs/{id}`；完成后从 `result.files[].url` 下载。下载也需要认证。同步客户端断开不会取消已提交任务，请使用 DELETE 取消。`wait=false` 队列满返回 429，模型未就绪返回 503，参数不合法返回 422。

调用示例（Python 调用方的环境由调用方自行管理）：

```python
import requests, time
s = requests.Session()
s.headers['Authorization'] = 'Bearer YOUR_API_KEY'
base = 'http://127.0.0.1:19876'
r = s.post(base+'/v1/music/generate?wait=false', json={
    'lyrics':'[Verse]\nHello world', 'style':'acoustic pop', 'count':1,
})
r.raise_for_status()
job = r.json()
while job['status'] in ('queued', 'running'):
    time.sleep(2)
    job = s.get(base+'/v1/jobs/'+job['id']).json()
if job['status'] != 'succeeded':
    raise RuntimeError(job.get('error'))
for i, item in enumerate(job['result']['files']):
    audio = s.get(base+item['url'])
    audio.raise_for_status()
    open(f'song-{i+1}.wav','wb').write(audio.content)
```

降噪先上传，再提交返回的 `upload_id`。不接受远程 URL 或任意本地输入路径，避免其他应用借接口读取不相关文件。上传原件、任务结果及 worker.log 当前保留供检查；请定期清理自己不需要的文件，尚未实现自动保留期限。

## 人声分离（双人语音）

与降噪使用不同模型：`MossFormer2_SE_48K` 做语音增强，新增的 **`MossFormer2_SS_16K`** 做两位说话人的混合语音分离。这与参考项目的 Speech Separation 节点一致；不是歌曲的人声/伴奏分离，也不进行视频人物追踪。

界面进入“人声分离”，选择音频或视频，点击“开始分离”。视频提取第一条音轨。成功后任务记录显示“说话人 1 / 2”，可分别试听、下载 **16 kHz 单声道 WAV**。音轨编号不是人物身份，不保证不同任务或长音频不同分段的说话人编号一致，长录音结果需试听检查。模型固定为两位说话人，没有人数或强度参数。

```json
{
  "upload_id": "上传接口返回的文件 ID",
  "segment_seconds": 2,
  "max_duration": 1800
}
```

提交到 `POST /v1/separate?wait=false`，或将同样参数作为表单字段连同 `file` 提交到 `/v1/separate/file?wait=false`。不传 `wait=false` 时同步等待完成。JSON 和 multipart 都使用现有 Bearer API Key。

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| segment_seconds | 2 秒 | 超过后触发分段推理，范围 2–120 秒；实际分段窗口沿用模型的 2 秒设置，并非降噪强度 |
| max_duration | 1800 秒 | 输入时长上限，范围 1–7200 秒，超出报错 |
| device | cuda | 服务配置中可切换 CPU |
| timeout_seconds | 1800 秒 | 服务级任务超时，范围 30–14400 秒 |

单次请求省略可选参数时使用服务配置。下载方法与原接口相同：异步任务成功后读取 `result.files`，同步返回 `files`。每项额外带有 `speaker`（1 或 2），同时包含 `url`、`sample_rate`、`duration`、`path`。音乐、降噪与分离共用串行推理队列，任务结束释放模型进程；分离权重缺失不会影响降噪。

## 独立环境与开发

`runtimes/python/` 内为 APP 专用 CPython 3.12.13；`runtimes/api`、`music`、`denoise`、`sfx`、`tts`、`vc` 各有独立 site-packages，均不启用 system-site-packages。版本锁定在 `requirements/*.lock.txt`。FFmpeg 也是 APP 内独立副本。运行时推理禁用 Hugging Face 自动下载。

重新准备（PowerShell，首次下载需要网络、磁盘空间和 NVIDIA 驱动）：

```powershell
./scripts/setup-runtime.ps1 -FFmpegSource '<path-to-ffmpeg.exe>' -DownloadDenoiseModel -DownloadSeparationModel
npm ci
./scripts/build.ps1
```

脚本会在 `runtimes/` 安装独立解释器和依赖，不向系统 Python 安装包。FFmpeg 请提供可信来源的静态 Windows 构建。CUDA PyTorch 体积较大，缓存也保留在 APP 内。无需启动完整 ComfyUI HTTP 服务，仅从独立 runtime 导入推理模块；不加载任何 custom_nodes。

开发：`npm run tauri dev`。单独 API：`runtimes/api/Scripts/python.exe server/run.py`（使用项目 `data/`），前端：`npm run dev`，浏览器中填入 `data/api-token`。桌面和单独 API 不应同时使用同一个端口。

测试依赖可以安装到 APP 的测试环境：`.venv/Scripts/python.exe -m pytest tests -q`。真实 GPU 验证脚本 `scripts/smoke_api.py` 需要预备测试音频/视频，只用于本地开发验证。

## 已验证与边界

- 前端 TypeScript/Vite 构建与 Rust Tauri 编译通过。
- API 自动化测试覆盖鉴权、保存后重启、失败恢复、取消、音效分类/扫描/下载、Range 和路径越界。
- RTX 4090 上使用现有 YuE2 合并权重完成短音频生成，HTTP 异步任务一次生成两首且两首均可下载。
- MossFormer2 完成 25 秒音频分段推理；视频上传、提取音轨、降噪和下载端到端通过。
- 新增 SS_16K 分离服务：真实模型的分段/非分段推理、JSON/multipart 接口、两条 16 kHz 单声道音轨下载通过；原 SE_48K 降噪回归通过。这是合成音频/视频的流程验证，未用双人语音数据做分离质量评测。
- 13 项自动化测试通过，包含旧配置迁移、分离与降噪互不影响、分离参数校验与鉴权。可用 `.venv/Scripts/python.exe scripts/smoke_separation.py <短音频或视频>` 手动运行真实模型接口测试。
- 验证是功能短测，不代表长歌曲质量、所有媒体格式或低显存设备的性能保证。

## 上游与来源

- [Tauri v2](https://v2.tauri.app/) / [Lucide React](https://lucide.dev/guide/react)
- [Comfy-Org YuE2 权重说明](https://huggingface.co/Comfy-Org/YuE2)
- [YuE2 推理节点源码](https://github.com/Comfy-Org/ComfyUI/blob/7a0b5eede3f9721c8faab290689893f36edc6d66/comfy_extras/nodes_yue2.py)
- [参考节点项目：ComfyUI-ClearerVoice-Studio](https://github.com/freeyaers/ComfyUI-ClearerVoice-Studio) / [MossFormer2_SS_16K 权重](https://huggingface.co/alibabasglab/MossFormer2_SS_16K)
- [ClearerVoice-Studio](https://github.com/modelscope/ClearerVoice-Studio) / [MossFormer2_SE_48K](https://huggingface.co/alibabasglab/MossFormer2_SE_48K)

模型与运行库各自遵循上游许可；YuE2 权重标注 CC-BY-NC-4.0。重新分发 ComfyUI、FFmpeg、Python 和模型时需保留相应许可。桌面图标来自仓库内确定性 SVG，不使用 AI 生成；PNG 和 Windows ICO 内嵌 ImageAssetMetadata，记录无原始 AI 提示词，写入前备份并验证像素块不变。


### 音乐曲谱选项

`POST /v1/music/generate` 新增 `generate_score`，默认 `false`。例如：

```json
{"lyrics":"[Verse]\n晚风轻轻经过窗台", "style":"Mandarin pop", "mode":"full", "generate_score":true}
```

开启后，每首歌曲额外保存一份 ABC 曲谱。`full` 导出旋律与和弦规划，`melody` 导出旋律规划；`mode=off` 与 `generate_score=true` 不兼容，返回 422。关闭导出不改变原有乐谱规划和音频生成过程。

同步响应新增 `scores` 数组，异步任务成功后读取 `result.scores`。未开启时为空数组。每项包含 `audio_index`（对应 `files` 的零起始索引）、`format: "abc"`、`mode`、`path` 和 `url`。

- `GET /v1/jobs/{id}/scores/{index}`：返回 JSON，包含 `abc` 原文、`format`、`mode`、`audio_index`。
- 同一路径加 `?download=true`：下载 `.abc` 文件。
- 所有曲谱读取与下载均需要 Bearer API Key；文件缺失或索引无效返回 404。

音乐生成页提供“生成曲谱”开关，任务完成后可选择歌曲查看五线谱、ABC 原文及下载。显示由随应用打包的 abcjs 在本地完成。旧任务不自动补导出。模型产生不规范 ABC 时显示提示并保留原文下载。

曲谱是生成阶段的旋律 / 和弦规划，并非从最终音频转录出的完整乐队总谱，可能与演唱、伴奏或截断后的音频不同。YuE2 底层支持将编辑后的 ABC 输入重新生成歌曲；应用提供 ABC 编辑框、“预览修改”和“按此曲谱重新生成”。新任务沿用原参数和对应歌曲的种子，生成 1 首新歌，保留原文件。输入曲谱时不运行规划器，规划 LoRA 被移除，声学 LoRA 保留。


改谱仅限桌面应用，不提供对外 API。公开 `/v1/music/generate` 不接受 `abc` 参数（返回 422）。桌面内部通道使用独立凭据，普通 Bearer API Key 无法调用，且不出现在 OpenAPI 中。


音乐请求新增可选 `title`（最多 120 字符）。留空或全空格时，以任务提交时本机时间按 `yyyyMMdd-hhmmss_n` 命名（24 小时制，n 从 1 开始）；填写时单首使用原歌名，两首分别追加 `_1`、`_2`。歌曲和曲谱结果包含 `title`，文件名中的 Windows 非法字符替换为下划线。排队时即确定名称，同名任务保存在各自任务目录中。音乐页右侧显示歌曲列表、状态、播放与下载，提交后留在音乐页。

歌曲列表支持逐首重命名、创建或选择分组、取消分组（留空）及分组筛选。元数据独立保存在 SQLite 中，排队与生成中也可修改，任务完成不会覆盖修改；原文件及下载 URL 保持不变，应用下载采用新名称。最近 200 条任务范围内显示歌曲。

作品区采用两级导航，默认 `Workspaces > 未分组`。点击 `Workspaces` 返回可搜索的工作区列表，第一项为“创建工作区”；空工作区也保存到 SQLite，已有分组自动显示为工作区。进入具体工作区后，新歌、参考重生成及改谱生成自动归入该工作区；在列表页或未分组内生成则放入未分组。通过歌曲的“更多 → 移动至”选择工作区（含未分组），即可移动已有作品。歌名后的铅笔图标可直接编辑歌名，回车或勾号保存，Esc 或叉号取消。计数与列表目前仅涵盖最近 200 条任务。

已完成的音轨支持独立设置 1–5 星评分与收藏，保存在 SQLite，重启后保留。再次点击当前星级可清除评分。顶部紧凑工具栏可搜索当前工作区的歌名和风格，“筛选”面板显示已启用条件数量并支持重置；搜索范围为最近 200 条任务中已加载的音轨。工作区内可组合使用星级、仅看收藏与音轨类型标签筛选。星星未选中表示全部，再次点击当前星级取消筛选；音轨类型标签同样可再次点击取消，未选中时显示全部音轨；原曲、分离后的人声与伴奏分别标注。

表单编辑时自动保存本地草稿，再次打开恢复上次页面、工作区、生成文字、选项及参考音视频（通过 IndexedDB 缓存）；移除参考文件也会清除对应缓存。恢复草稿不会自动提交任务或应用未保存的服务配置。桌面端和浏览器草稿独立，清除应用/浏览器存储会删除草稿；空间不足时大型媒体可能无法缓存。

歌曲作品库支持 Cover、Remix、改曲、改词和复用参数，采用左侧创作、右侧作品库的交互。来源歌曲与生成方式在左侧提示卡中显示，修改后点击“生成新版本”，保留原作品。

- **Cover**：读取原音频，用配置的 SheetSage2 提取不含和弦的旋律 ABC，以新风格和歌词重新生成。
- **Remix**：从原音频提取旋律与和弦，以修改后的风格重新编曲；不是分轨混音台。
- **改曲**：需要已保存曲谱，回填原 ABC，允许修改音符、节奏、调号和和弦，也可修改歌词、风格。
- **改词**：回填歌词；优先参考原曲谱，无曲谱时从原音频转谱。整首重新生成，不能保证只替换某个字或音频片段。
- **复用参数**：仅回填歌名、歌词、风格、种子及页面选项，独立生成，不引用原音频或曲谱。

参考生成跳过规划 LoRA，声学 LoRA 可用。SheetSage2 转谱和 YuE2 生成依次执行，完成转谱后卸载转谱模型；共享现有串行队列，任务结束释放进程。SheetSage2 缺失时返回配置提示，不影响普通文本生成。原音频不是声音克隆条件，无法保证原音色不变；转谱也可能有误差。歌曲的版本关系记录在任务的 source_job_id / source_audio_index 中。

上述改编、改曲和改词均仅供桌面应用使用，独立内部凭据鉴权，不在公开 OpenAPI 中提供接口。公开音乐接口仍不接受 ABC 或参考音频。当前不提供 Suno 的局部音频替换、续写、分轨混音或音色 Persona。


新增 **AuK 音频编辑**（第 8 个服务），提供语音/清唱内容编辑、情绪音色调整、增强与分离等操作。当前模型和独立依赖待配置，详见 [AuK 接入说明](docs/auk.md)。


界面现支持简体中文、英文和日语，默认跟随系统，在“应用设置 → 界面语言”中可手动切换并自动保存，立即生效。详见 [i18n 说明](docs/i18n.md)。

### 音乐参考音频
在音乐生成页左侧拖入音频或视频，或点击上传，支持 WAV、MP3、FLAC、OGG、M4A、AAC、OPUS、MP4、MOV、MKV、WEBM、AVI（单文件不超过 512 MB、音乐参考最长 15 分钟）。音乐参考、Qwen/Breeze 参考音色、音色转换参考和 AuK 输入统一支持音频/视频选择与拖放。选择视频后会自动上传，由后台提取第一条音轨，预览前 30 秒的 WAV 音频，不显示视频画面；正式生成复用原始上传文件，遵循各模型原有时长限制，不使用截短的预览。没有音轨或音轨无法解码时显示错误。预览需要配置 FFmpeg，无需加载 AI 模型。认证接口 `POST /v1/uploads/{upload_id}/audio-preview?service=music` 同时支持 `tts`、`vc`、`auk`，返回含预览 WAV 的 `audio_base64`，编码后清理临时预览文件。
选择“仅旋律”参考旋律，选择“完整规划”参考旋律与和弦，再结合填写的歌词、风格重新生成。参考音频不自动识别歌词、不复制音色，也不是原曲续写。使用 SheetSage2 和音乐服务配置中的 FFmpeg；不可同时使用直接生成或规划 LoRA，声学 LoRA 仍可使用。
外部音频参考通过桌面内部接口 `/internal/music/reference` 接入，不增加公开 API。

### Windows 启动环境与历史数据（2026-09-17）
从 Codex（MSIX 应用）启动时，Windows 可能将 Roaming 数据重定向至 Codex 的 LocalCache；直接启动则读取真实用户 Roaming。已将隔离目录中的历史任务及音频补充到当前直接启动服务，原目录保留，恢复前 SQLite 快照位于 data/recovery-20260917-232115。尚未切换固定数据根目录，避免重启中断运行任务。后续从 Codex 管理服务时，应通过正常 Windows 进程环境检查实际数据库与 API，不应将重定向后的文件误认为当前服务数据。

统一 Qwen3-TTS / Breeze TTS 2 API、自动模型下载与共用环境说明见 [docs/tts-api.md](docs/tts-api.md)。

### 歌曲人声与伴奏分离
在音乐生成页的原曲卡片点击“人声分离”，会创建串行分离任务。完成后新增人声、伴奏两条 44.1 kHz 立体声 WAV，保留来源关联与分组。音轨类型筛选支持全部、原曲、人声、伴奏，分离结果支持独立重命名、分组、试听和下载。已在排队或运行的同一首歌不会重复提交。
使用官方 TorchAudio HDemucs 歌曲分离模型，和 YuE2 共用音乐 Python 环境；不会加载 YuE2。权重可在音乐配置中修改，默认位于 runtimes/models/HDemucs/hdemucs_high_trained.pt；默认文件缺失时首次分离会从 PyTorch 官方地址下载。分离按片段交叠处理，每任务结束释放模型。模型结果可能残留伴奏或人声，并非无损分轨；它与 MossFormer2 的双说话人语音分离是不同功能。

桌面版音频与曲谱下载使用原生另存为窗口；用户选择位置后写入原始文件字节，完成后提示保存路径。取消另存为不会创建文件。浏览器预览保留浏览器下载方式。

Windows 桌面版的生成结果新增“打开文件夹”：在文件资源管理器中打开原始输出目录并选中文件。歌曲列表、任务结果明细、AuK 结果和曲谱面板均可使用；文件不存在或已移动时显示错误。浏览器预览不显示此桌面按钮。

歌曲及分离音轨的标题旁显示蓝色圆点，表示尚无播放记录。只有应用内音频实际开始播放才清除，下载或播放失败不会标记已播放。状态按音轨存入 SQLite，重命名、分组和重启不丢失。历史歌曲此前没有播放记录，初始也显示圆点；外部播放器的播放无法检测。

人声分离页面支持“两位说话人”（MossFormer2 SS 16K）、“人声＋伴奏”（复用音乐服务的 HDemucs）和“同时执行两者”。两者模式要求两个服务均就绪，一次排入两个任务并依次运行，在任务记录中分别显示四条带标签、可独立播放的音轨。HDemucs 支持最长 15 分钟，输出 44.1 kHz 立体声 WAV；说话人分离输出 16 kHz 单声道 WAV。

### 分离 API 模式参数

`POST /v1/separate` 增加可选 `mode`：`speakers`（默认，两位说话人）、`music`（人声＋伴奏）、`both`（两个任务，共四条音轨）。`/v1/separate/file` 同样支持 multipart 表单字段 `mode`。使用 Bearer API Key 认证。

```json
{"upload_id":"上传返回的文件ID","mode":"both"}
```

`?wait=false`：单模式仍返回原来的任务对象；`both` 返回 HTTP 202 和 `{ "mode": "both", "jobs": [...] }`，按各任务 ID 查询 `/v1/jobs/{id}`。默认 `wait=true`：两者模式等待两个任务结束，返回 `status`、`jobs`、合并的 `files`（成功共四条）。任务失败返回 HTTP 500，保留已完成的结果。部分提交失败时返回 `status: "partial"` 和已接受的 `jobs`。

可选 `title` 用于人声／伴奏命名。`segment_seconds`、`max_duration` 仅用于两位说话人模式；HDemucs 使用已有的固定分块和 900 秒时长上限。音乐模式要求音乐服务就绪；两者模式要求两个服务就绪，经共享队列依次运行。

“配置”左侧播放模式按钮按“顺序播放（默认、不循环）→ 单曲循环 → 列表循环”切换。歌曲队列采用点击播放时当前工作区、搜索和筛选后的列表顺序；顺序播放到末尾停止，列表循环回到第一首。播放模式保存在本地，重启不自动开始播放。
