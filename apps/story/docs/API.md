# 剧本与分镜 Agent API

默认地址 `http://127.0.0.1:19878`，仅监听本机。`/docs` 是交互式文档，`/openapi.json` 提供字段 schema。业务接口必须带 `Authorization: Bearer <token>`。

桌面应用与开发服务使用同一数据目录，Token 在应用根目录 `data/story/api-token`。这是剧本应用自己的 Token，不是图片或音频应用的 Token。不要将 Token 放入 URL、项目文件或提示词。

## 读取范围

| 方法与路径 | 内容 |
| --- | --- |
| `GET /health` | 无需认证的存活检查 |
| `GET /v1/projects` | 已打开的剧、项目 ID、名称和目录 |
| `GET /v1/projects/{id}` | 整部剧的完整可保存文档，包含 revision |
| `GET /v1/projects/{id}/content` | 整部剧的章节、剧本、分镜和资产 |
| `GET /v1/projects/{id}/content?chapter_id=...` | 指定季／章，包含所有话的剧本和分镜 |
| `GET /v1/projects/{id}/content?episode_id=...` | 指定话；可与 chapter_id 一起限制范围 |
| `GET /v1/projects/{id}/content?include_assets=false` | 省略资产列表；默认包含 |
| `GET /v1/projects/{id}/media/{filename}` | 已导入的项目素材（需要认证） |
| `GET /v1/skill` | 实际发送给文字模型的文字分镜 Skill |

范围读取的文档仍带整部剧的 revision。**不能把范围读取结果 PUT 回整部剧**，否则会替换掉未返回的章节。局部编辑用 PATCH 或事务接口。

## 创建与局部修改

所有修改体必须带最近读取的 `revision`。成功返回新 revision、受影响的 `ids` 和完整 `project`。每次调用在同一把项目存储锁中执行“检查版本 → 验证 → 历史快照 → 原子写入”。`reason` 和 `actor` 会记入历史。

| 方法与路径 | 行为 |
| --- | --- |
| `POST /v1/projects/open` | `{directory, name}` 创建剧；省略 name 打开目录内 story.json |
| `POST /v1/projects/{id}/chapters` | 创建季／章 |
| `POST /v1/projects/{id}/chapters/{chapter}/episodes` | 创建话／特别篇 |
| `POST /v1/projects/{id}/episodes/{episode}/shots` | 创建镜头 |
| `POST /v1/projects/{id}/assets` | 创建资产 |
| `PATCH /v1/projects/{id}/chapters/{target}` | 局部更新季／章 |
| `PATCH /v1/projects/{id}/episodes/{target}` | 局部更新话，例如 script |
| `PATCH /v1/projects/{id}/shots/{target}` | 局部更新分镜，例如 dialogue、duration |
| `PATCH /v1/projects/{id}/assets/{target}` | 局部更新资产；角色改名同步关联分镜的说话人 |
| `PUT /v1/projects/{id}` | 替换完整文档，需要原始完整内容与最新 revision |

例：新增季。

```json
{"revision":12,"actor":"Codex","reason":"新增第二季","data":{"title":"第二季"}}
```

例：更新某话的文字分镜剧本。

```json
{"revision":13,"actor":"Codex","reason":"优化雨夜开场","data":{"script":"1-1 废弃仓库 [内] [夜]\n镜1（全景 / 平视 / 固定）3秒\n△ 陈墨推开铁门。"}}
```

## 多项修改的原子事务

`POST /v1/projects/{id}/transactions`。一次请求最多 200 个操作，仅产生一次版本变化和一条历史记录。任何操作失败，全部不写入。

```json
{
  "revision":14,
  "actor":"Codex",
  "reason":"调整对话节奏并添加反应镜头",
  "operations":[
    {"action":"update","entity":"shot","id":"真实镜头ID","data":{"dialogue":"等等！","duration":2}},
    {"action":"create","entity":"shot","parent_id":"真实话ID","data":{"title":"回头","description":"陈墨停下脚步，回头望向门口。","duration":3}}
  ]
}
```

`entity` 支持 chapter、episode、shot、asset、project；`action` 支持 create、update、delete。project 仅允许 update name、width、height、fps、style。新建 ID 由服务产生。create episode 的 parent_id 是章 ID，create shot 是话 ID。删除仍被镜头引用的资产会返回 409，需先在同一事务中移除引用。更改数组字段会替换整个数组；优先用针对实体的操作，以保留未涉及内容。

冲突：HTTP 409，重新 GET 最新内容，合并自己的修改后再发送。不要仅把 revision 改为最新值盲目重试。非法字段／未知资产／不正确时长返回 422。媒体文件先上传，不能伪造文件路径。历史不会删除媒体文件，故恢复旧版本仍可访问原素材。

## 历史与恢复

- `GET /v1/projects/{id}/history`：版本、修改时间和原因。
- `GET /v1/projects/{id}/history/{version}`：完整旧快照，version 为列表返回的八位字符串。
- `POST /v1/projects/{id}/history/{version}/restore`：请求 `{ "revision":当前版本 }`。恢复产生新版本，当前状态也被保留，不回退 revision 计数。
- UI 未编辑时每四秒同步外部 Agent 保存的最新版本；有未保存内容时保留草稿，冲突不会自动覆盖。

## 文字 Agent 与导入

`POST /v1/import-script`：multipart 的 `file`，支持 .md/.markdown/.txt，UTF-8（含 BOM）或 GB18030。只返回解析章节，不直接改项目。无标题文本保存为单话，正文不删改。

`POST /v1/projects/{id}/agent`：`{mode:"rewrite"或"shots",content:"选区或整话正文",instruction:"用户说明"}`。rewrite 返回 `{text}`，shots 返回校验过的 `{shots}`。这只是提案，调用方检查后通过 PATCH／事务应用。服务每次实际加载内置 Skill，不把“使用 Skill”仅作为界面文案。

## 生成图片与角色素材

`POST /v1/projects/{id}/media` 上传图片或声音；返回项目相对 `path` 及 `metadata`。图片像素不重编码，不臆造历史图片的原始提示词。PNG 读取 ImageAssetMetadata；缺失时在项目副本中写入 `generation_prompt: null`、`generation_prompt_status: unavailable` 并备份原上传字节。已有不兼容记录会保留并返回 warning。JPEG/WebP 可以保存，但当前不解析或重写其 XMP。

`POST /v1/projects/{id}/generate`：`{kind:"asset"或"shot"或"board",target_id:"资产ID／镜头ID／话ID",prompt:"补充说明",shot_ids:[]}`。board 最多选择 9 镜，生成一张连续多格总览图；它不等于生成九个独立文件。shot 每次产生一张可绑定的效果图。接口调用独立 image 应用，模型和显存由 image 管理。

新生成 PNG 在保存到项目时插入完整实际提示词、参考记录，设定图另存描述和一致性要求。写入前备份，写入后验证像素／颜色／透明通道关键数据摘要与元数据回读。保留已有 ComfyUI prompt/workflow。设定描述来源为用户设计文档，需人工核对成图，不冒称视觉识别结果。

## 对白转语音

`GET /v1/audio/voices`：代理音频应用的音色列表。

`POST /v1/projects/{id}/speech`：`{"shot_id":"真实镜头ID","revision":当前版本,"use_reference":true}`。

服务从镜头读取 **dialogue 正文**，不会朗读 speaker、emotion、delivery、O.S. 或 V.O. 字段。角色按 speaker 精确匹配；同名歧义拒绝生成。优先用角色 voice 文件和 voice_reference_text 做克隆，否则使用 voice_preset；无角色时使用默认音色。`use_reference:false` 强制预设模式。

- Qwen3-TTS 预设模式：voice_description 和 emotion 进入 instruct；克隆模式不支持 instruct，会明确返回 warning。
- Breeze TTS 2：用声音描述和情绪设计音色；克隆必须填写准确参考原文。
- 一镜一个说话人。多人对话请拆镜，避免把角色名前缀朗读为台词。
- 完成的 WAV 保存到项目；应用前校验对白和说话人仍与提交时一致，否则 409。
- 不自动改变镜头时长。UI 提供“镜头匹配音频时长”；导出拒绝把较长配音硬截断。对白变化后旧配音标为过期，导出不使用旧配音。

## 任务、应用与导出

- `GET /v1/projects/{id}/jobs`：图片／配音任务记录。
- `GET /v1/projects/{id}/jobs/{jid}`：同步上游状态，完成时下载结果并验证。关闭 UI 后上游继续执行；再次查询可恢复结果。需保持原图片／音频服务可访问。
- `POST /v1/projects/{id}/jobs/{jid}/cancel`：取消上游任务。
- `POST /v1/projects/{id}/jobs/{jid}/apply`：`{"revision":当前版本}`，将完成结果绑定回原实体，同时创建历史。
- `GET /v1/projects/{id}/export/{episode}?group=true`：包含 project.json、storyboard.json、media/images、media/audios 的 ZIP。group=true 合并相邻同场镜头，false 一镜一 Clip。禁用镜头保留分镜记录但不生成可运行 Clip。配音生成 audio 轨，字幕标记为估算时序。遵循 Timeline 0.17.23、project schema 4、storyboard schema 1。

设置：`GET/PUT /v1/settings`。文字模型支持 Ollama 与 OpenAI 兼容接口；图片、音频仅允许本机地址，远程文字接口要求 HTTPS。设置含私密密钥，不应发给语言模型或写入项目。使用远程文字接口意味着将所选正文和资产文字描述发送给用户配置的提供商。

## Python 调用示例

设置 `STORY_APP_ROOT` 为运行应用的根目录。完整创作流程见 [外部 Agent Skill](../skills/story-agent/SKILL.md)。

```python
from pathlib import Path
import os, requests
token = (Path(os.environ['STORY_APP_ROOT'])/'data/story/api-token').read_text().strip()
s = requests.Session()
s.headers['Authorization'] = 'Bearer ' + token
base = 'http://127.0.0.1:19878'
projects = s.get(base+'/v1/projects', timeout=10).json()
pid = projects[0]['id']  # 实际使用时按名称选择所需的剧
story = s.get(f'{base}/v1/projects/{pid}/content', timeout=10).json()
response = s.post(f'{base}/v1/projects/{pid}/chapters', json={
    'revision': story['revision'], 'actor': 'Codex', 'reason': '新增下一季',
    'data': {'title': '第二季'}
}, timeout=10)
response.raise_for_status()
print(response.json()['ids'])
```


创建项目 `POST /v1/projects/open` 只需 `{"name":"剧名"}`；`directory` 可选。`PUT /v1/settings` 的 `project_directory` 设置新项目素材根目录，留空使用应用数据目录。正文与历史保存在 `story.sqlite3`。提供目录但不提供 name 时，打开已登记项目或导入旧版 story.json。

`GET /v1/system/fonts`：读取本机安装的字体族，返回 `{ "fonts": ["Arial", "Microsoft YaHei"], "available": true }`。沿用 Bearer Token 认证；非 Windows 返回空列表及 `available: false`。


## 移动端网关

电脑管理 API（仍需桌面 Bearer Token，仅回环地址）：

- `GET /v1/mobile`：监听状态、可用局域网地址、待确认请求和已绑定设备。
- `PUT /v1/mobile`：`{"enabled":true,"port":19879}`，开启 / 关闭独立局域网网关。
- `POST /v1/mobile/pair`：`{"address":"192.168.1.10"}`，返回单次使用、5 分钟有效的绑定 URL 及 SVG 二维码。新建二维码使上一个二维码失效。
- `POST /v1/mobile/pending/{id}`：`{"approve":true}` 确认，`false` 拒绝。
- `POST /v1/mobile/devices/{id}/revoke`：撤销设备。

移动网关（默认 19879）单独鉴权。扫描 URL 的 fragment 后，手机以 `POST /pair/claim` 提交 `code` 和 `name`，得到请求 ID 与私密轮询 secret；`POST /pair/{id}/poll` 携带 secret，电脑确认后获得设备 Token。该 Token 仅存哈希于电脑 SQLite，90 天后过期，不能用于桌面 API。

移动 Bearer Token 可读取 `/v1/session`、`/v1/projects`、`/v1/projects/{id}`、项目媒体和历史版本；`PUT /v1/projects/{id}` 使用完整 Project 和最近读取的 revision 保存，版本过期返回 409，并通过 Store.save 生成历史。其他桌面功能不在移动网关注册。
