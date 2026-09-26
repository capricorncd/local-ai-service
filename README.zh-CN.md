# Local AI 应用集合

[English](README.md)

- [音频应用](apps/audio/README.zh-CN.md)：本地音乐与音效生成、文字转语音、音色转换、音频编辑、降噪和人声分离。
- [图片应用](apps/image/README.zh-CN.md)：图层编辑、遮罩、工程导入导出和本地 Qwen Image 2.1 推理。
- [图片 API](apps/image/docs/API.md)：上传、生成／编辑、工程及任务管理。
- [剧本与分镜应用](apps/story/README.zh-CN.md)：分季分话、文字分镜、资产设定、Agent 修改、图片与对白配音、历史版本和 Timeline 导出。
- [剧本 Agent API](apps/story/docs/API.md)：整剧／季／话读取，章节和镜头的版本化修改，事务更新与历史恢复。

## 配合 ComfyUI 创作视频

如果你的电脑具备本地运行 ComfyUI 及所需模型的条件，推荐搭配 [ComfyUI-Capricorncd-Timeline](https://github.com/capricorncd/ComfyUI-Capricorncd-Timeline) 使用，将剧本、图片、配音和音乐串联成完整的视频创作流程。

你可以先在剧本应用中整理故事、角色与分镜，使用图片应用准备视觉素材，再通过音频应用制作对白、音效和 BGM，或修复生成视频中的音频。剧本应用支持导出包含素材与配音的 Timeline 工程包，方便进入 Timeline 继续生成视频片段、编排时间线、剪辑与合成；单独生成的图片和音频也可通过文件导入使用。

适合希望在本地制作 AI 短片、漫剧或音乐视频的创作者。前往 [ComfyUI-Capricorncd-Timeline 项目主页](https://github.com/capricorncd/ComfyUI-Capricorncd-Timeline) 查看安装方式与使用说明，根据所选模型准备相应的显存和运行环境。

## 开发运行

根目录 `npm run dev`、`npm run build` 默认操作音频应用。

剧本应用：`npm run story:tauri -- dev`；`npm run story:build` 构建前端，`npm run story:test` 运行接口测试。API 使用独立端口 19878，创建项目时指定存储目录；图片生成与对白配音分别复用 19877、19876 的图片和音频应用。

图片应用：先运行 `apps/image/scripts/setup.ps1` 安装依赖，再执行 `npm run image:tauri -- dev`。`npm run image:build` 构建图片前端，`npm run build:all` 构建全部应用的前端。图片 API 使用 19877 端口，音频 API 使用 19876；模型配置、历史记录和桌面标识分别独立。
