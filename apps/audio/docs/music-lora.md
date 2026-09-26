# YuE2 可选 LoRA

音乐生成页面提供三种选择：

- **不使用 LoRA**：默认，保持基础模型行为。
- **speedyrulz**：支持声学（MODEL）及规划（CLIP）LoRA，可只选一种，也可同时加载。
- **Starnodes2024**：支持声学 LoRA，建议将乐谱规划设为“直接生成 / off”。页面提供切换按钮，不会静默改变规划模式。

本功能加载这两个训练项目导出的**原生 ComfyUI 格式 `.safetensors`**。本次不提供训练按钮，不启动训练，也无需安装两个训练器到已有 ComfyUI 中。方案选项描述可用类型，不验证文件作者；旧版未转换的训练器内部格式会报错，需要由原训练工具导出为原生格式。

## 使用

1. 在“音乐生成 → 配置”中设置 **YuE2 LoRA 目录**，默认 `runtimes/models/YuE2-LoRA`。修改目录后保存并重启音乐服务。
2. 将已经训练好的 LoRA 放入该目录或子目录，点击“刷新文件”。新增文件无需重启服务。
3. 选择方案和文件。声学、规划权重默认 **1.0**，范围 **0–3**；0 不应用对应部分。没有文件时无法提交启用 LoRA 的任务；可以切回“不使用 LoRA”正常生成。
4. 如训练时使用了触发词，将触发词写在“音乐风格”中。程序不自动执行或拼接文件元数据。

声学 LoRA 影响音色、乐器与制作质感；规划 LoRA 影响旋律、和声及结构。speedyrulz 的合并文件可同时选入两栏，各自只应用相应部分。两项采用同一文件时只读取一次。

## 接口

`GET /v1/music/lora-options` 返回方案、当前生效的目录、目录是否存在以及文件列表。文件的 `targets` 为 `acoustic` / `planner`，不支持的文件附带 `error`，不会加载到模型。列表仅解析有大小上限的 safetensors 文件头，不加载模型或占用 GPU。所有业务接口均需 Bearer 认证。

`POST /v1/music/generate?wait=false`：

```json
{
  "lyrics": "[Verse]\n晚风轻轻经过窗台",
  "style": "my_style, Mandarin, acoustic pop",
  "lora_provider": "speedyrulz",
  "acoustic_lora": "my-acoustic.safetensors",
  "acoustic_strength": 1.0,
  "planner_lora": "my-planner.safetensors",
  "planner_strength": 0.8,
  "mode": "full",
  "count": 1,
  "seed": 42
}
```

`lora_provider`：`none`（默认）、`speedyrulz`、`starnodes2024`。文件名为配置目录下的相对路径，拒绝绝对路径、越界路径及非 safetensors 文件。启用方案后至少选择一个文件，Starnodes2024 不接受规划文件。省略这些字段的旧请求仍按原方式生成。

结果中增加 `lora_provider` 和 `loras`，每项含 `target`、`file`、`strength`、`matched_layers`、`applied`。权重形状、数值及匹配层会在推理进程中检查，不匹配即使任务失败，避免无声地忽略 LoRA。文件缺失或类型不符会在入队前报错。每个任务用新进程加载基础模型，LoRA 不会残留到后续任务，也不会改写 checkpoint。

## 验证

自动测试覆盖两方案、默认关闭、类型限制、文件列表、认证、目录生效规则、路径越界和损坏文件头。`scripts/smoke_lora.py` 使用当前 YuE2 checkpoint 与合成测试适配器检查实际权重增量及 0 权重行为。测试适配器保存在 `data/smoke-lora`，不放入可选目录，不作为训练好的音色或风格提供。实际训练 LoRA 的音质仍需用你的文件试听确认。

项目来源：[speedyrulz](https://github.com/speedyrulz/ComfyUI-YuE2-Trainer)、[Starnodes2024](https://github.com/Starnodes2024/ComfyUI-YuE2-Trainer)。
