# 统一文字转语音 API

`POST /v1/tts/generate?wait=false`，使用现有 `Authorization: Bearer <API_KEY>`。
`model` 可选 `qwen3-tts` / `breeze-tts2`，不传时仍为 Qwen，兼容已有调用。
省略 `wait=false` 则等待结果；异步返回 202，轮询 `/v1/jobs/{id}`。
两种模型返回相同的 `files` 数组及下载 URL，结果中的 `model` 标识实际模型。

## Qwen 预设音色

```json
{"model":"qwen3-tts","text":"你好，欢迎来到故事世界。","speaker":"serena","language":"Chinese","instruct":"温柔自然","seed":42}
```

## Breeze 文字设计音色

```json
{"model":"breeze-tts2","text":"[笑] 今天我们要去探险！","language":"Chinese","instruct":"年轻活泼的女性，声音明亮，带着期待和笑意。","cfg_scale":4,"seed":42}
```

## Breeze 克隆及表演控制

先向 `/v1/uploads` 上传参考音频，取得 `upload_id`：

```json
{"model":"breeze-tts2","text":"我终于找到你了。","reference_upload_id":"上传接口返回的ID.wav","reference_text":"参考录音完整且准确的原文。","instruct":"轻声、激动但克制，语速稍慢。","cfg_scale":4}
```

省略 `instruct` 是普通克隆，提供它则同时控制表达。Breeze 要求准确的参考文字；应用参考音频限制为 3–30 秒。`language` 接受 Chinese/English/Auto，用于能力校验，上游根据输入文字判断语言。

Qwen 克隆使用相同的 `reference_upload_id`、`reference_text`，文字可选；不能与 `speaker` 或 `instruct` 同传。Breeze 不接受 Qwen 的 speaker、temperature、max_new_tokens；Qwen 不接受 Breeze 的 cfg_scale。错误组合返回 422，不静默忽略参数。

`GET /v1/tts/models` 返回模型能力、配置状态及 Breeze 下载进度。Breeze 未配置不影响 Qwen；Qwen 未就绪不阻止已配置的 Breeze。

## 自动下载与运行环境

在文字转语音页选择 Breeze，点击“下载 Breeze 模型”。按钮使用桌面内部接口，下载源固定为官方 `BreezeBlue/Breeze-TTS-2` Hugging Face 仓库；将解析到的 commit 固定用于本次下载。下载显示文件名、字节进度，可取消并重试。完整文件通过大小与 LFS SHA-256 校验后才会替换正式文件；重试复用已验证文件，未完成的单个文件重新下载。

文件保存到 `runtimes/models/Breeze-TTS-2`，完成后自动保存模型目录配置，再手动重启 TTS 服务。下载不会加载模型或中断生成任务，失败时显示原因；关闭应用会停止下载。不要在下载过程中手动修改下载目录中的文件。

Qwen 与 Breeze **共用现有 TTS Python 环境**（`tts.python`），没有增加 Breeze 虚拟环境。Breeze 可独立配置代码目录、模型目录、输出目录、CFG 和加速模式。两个模型均走现有串行任务队列，每个任务结束释放进程与显存。其他模型的 NumPy / Transformers 版本存在冲突，尚未合并其环境；全部环境仍属于本 APP，不使用系统 Python。

本机已通过两种模型在同一个环境内的导入检查；未下载 Breeze 权重，尚未验证 Windows 完整推理。官方支持 Linux。默认关闭加速模式。

Breeze 模型权重及本地输出适用官方非商业许可：
https://huggingface.co/BreezeBlue/Breeze-TTS-2/blob/main/LICENSE
官方代码：https://github.com/breezeblue-ai/breeze-tts
