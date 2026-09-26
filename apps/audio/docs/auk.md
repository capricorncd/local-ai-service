# AuK 音频编辑

应用新增独立 `auk` 服务和“音频编辑”页面，使用腾讯官方 AuK Python 接口。与其他推理任务共用串行队列，每任务独立进程；启动时只检查配置，不加载模型。公开业务接口需要 Bearer API Key。

当前已接入代码、页面与接口，模型和专用 Python 依赖尚未安装，没有进行真实 AuK 模型推理验证。未就绪时显示待配置，不影响其他服务。

## 环境与模型

运行 `scripts/setup-auk.ps1` 安装 APP 内的独立 Python 3.10 与 AuK 依赖。脚本不下载模型、不改动现有 ComfyUI 或其他服务环境，缓存也放在 APP 内。联网安装完成后会做导入检查。

配置项：

- Python：`runtimes/auk-env/Scripts/python.exe`
- 模型目录：默认 `runtimes/models/AuK`，含 `config.yaml`、`vae.safetensors`、`auk_base.safetensors`；或指向含 `auk_flash.safetensors` 的 Flash 目录。
- Qwen 目录：完整的 `Qwen/Qwen2.5-Omni-3B`，包括权重、tokenizer、processor。Qwen3-VL、Qwen Image 不可替代。
- 输出目录、FFmpeg、设备、CPU 卸载、步数、CFG 与超时分别配置。Base 默认 32 步、CFG 2；Flash 自动固定 4 步、CFG 0。

模型配置保存后手动重启 AuK 服务。推理设置本地离线模式，不自动下载缺失权重。不启用上游依赖外部 LLM 的 Prompt Enhancer 或云 ASR。

## 操作与限制

支持模板：语音内容替换/插入/删除、清唱歌词编辑、音高、语速、音量、情绪、描述音色、去口音、非语言声音、耳语转换、降噪去混响、说话人分离、歌曲人声提取、目标说话人提取、描述式 TTS、参考音色 TTS、自定义指令。模板只负责填写指令，不保证模型每次精确遵循。

输入音频或含音频视频，从指定起点截取片段；输入片段与生成输出合计不得超过 30 秒。默认输入 10 秒、输出 10 秒。输出只有处理后的片段，不自动拼回原音频。速度变化需手动调整目标时长。歌词编辑必须输入无伴奏清唱；混合歌曲先提取人声。没有宣称支持整首歌无损改词或确定性剪辑。

## API

`POST /v1/audio/edit?wait=false`：返回 202 任务；不带 `wait=false` 则等待任务完成。

```json
{"task":"content","instruction":"把‘你好’改成‘欢迎回来’。","upload_id":"先通过 /v1/uploads 上传得到的 ID","clip_start":0,"clip_seconds":10,"gen_seconds":10,"seed":42}
```

`task` 可用值见 OpenAPI。`tts` 不需要输入音频，`custom` 音频可选，其他类型必需。`steps`、`cfg` 省略时使用服务配置。结果通过 `result.files`（异步）或 `files`（同步）试听下载，沿用现有任务查询、取消和鉴权。

上游：[官方代码](https://github.com/Tencent-Hunyuan/AuK)、[操作说明](https://github.com/Tencent-Hunyuan/AuK/blob/main/docs/COOKBOOK.md)。
