# Local AI · 剧本与分镜

独立的第三个应用。按「剧 → 章／季 → 话／特别篇」管理 AI 漫剧，创建时可填写剧名；留空使用项目 UUID，素材目录可选，也可在设置中指定默认目录。

- Markdown／文本导入、文字分镜编辑、选区 Agent 优化、Skill 驱动拆镜，建议预览后应用。
- 角色／场景／道具资产、设定描述、参考图、角色参考录音与预设音色。
- 分镜景别、角度、运镜、光线、时长、对白、情绪、音效、字幕；默认画幅 1376×768。
- 输入 @ 搜索并引用资产，悬停查看大图；image 应用生成设定图、单镜效果图和连续多格故事板。
- 音频应用把对白生成 WAV，试听并关联镜头；可手动按实测音频长度调整镜头时长。
- 自动保存、未保存草稿恢复、完整历史查看与恢复；对外 Agent API 支持版本检查和事务更新。
- 导出包含实际素材与配音的 Timeline 工程 ZIP（0.17.23 / project v4 / storyboard v1）。字幕时间为估算，需配音后校准。

## 使用

在仓库根运行 `npm run story:tauri -- dev`。发布构建为 `npm run story:tauri -- build`，根目录 `Local-AI-Story.exe` 可直接启动（依赖本仓库的 Python 运行环境与服务源码）。

浏览器开发：先执行 `apps/story/scripts/start.ps1`，再 `npm run story:dev`，访问 `http://127.0.0.1:1422`，填入 `data/story/api-token`。桌面版无需手填 Token，与开发服务统一使用应用根目录 `data/story`。默认 API 端口 19878。

运行环境复用仓库的 `runtimes/image/Scripts/python.exe`，不加载图片模型；缺依赖时运行 `apps/story/scripts/setup.ps1`。图片和音频应用需要分别启动并完成各自模型配置。Ollama 需运行且填写实际已安装的模型名称；远程 Qwen 可选 OpenAI 兼容接口，填写其地址和 Key。

## 文件与接口

正文、分镜、资产文字和完整历史保存在应用数据目录的 `story.sqlite3` 中，当前版本与历史在同一事务内保存。素材保存在项目的 `media/`，生成任务记录在 `jobs/`。未指定目录时使用设置中的默认目录，未设置则使用应用数据目录的 `projects/<项目ID>`。已有 `projects.json` / `story.json` 与历史会在读取时迁入数据库，原文件保留备份，此后不再作为正文存储。备份项目需包含数据库和素材目录。

- [Agent API 与调用示例](docs/API.md)
- [文字分镜 Skill](skills/comic-script/SKILL.md)

测试：`npm run story:test`。前端构建：`npm run story:build`。

Logo 由内置 imagegen 生成，已将实际完整提示词写入源 PNG 和派生 PNG 图标，并按 image-metadata 技能备份、回读和验证像素摘要。Windows ICO / macOS ICNS 是由 Tauri 工具派生的容器；当前元数据工具不支持对这些容器嵌入同一记录，来源记录保留在对应 PNG 中，不声称容器已嵌入。

项目名称不可重复（忽略首尾空白与大小写）。项目改名时素材目录同步改名，已有同名目录会拒绝覆盖。目录名中的文件系统禁用字符会替换为短横线。

字体与字号：在右上角设置中的「字体与字号」调整，默认基础字号为 16 px，可选 12–24 px。可搜索并选择 Windows 已安装字体，立即生效并保存在本机。界面的字体、按钮尺寸、内边距、圆角和图标使用 rem 随基础字号缩放；屏幕百分比和视口布局保持自适应。根字号本身以 px 设置，不改变分镜输出图片的像素尺寸。

桌面正式版启用开发者工具：在页面右键选择‘检查（Inspect）’，切换到 Console 查看浏览器日志。菜单名称随系统语言显示。
