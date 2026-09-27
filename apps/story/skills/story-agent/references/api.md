# API 操作与字段

## 连接和返回值

默认 `BASE=http://127.0.0.1:19878`。`GET /health`、`GET /openapi.json` 无需令牌；业务请求使用 `Authorization: Bearer <token>`。JSON 请求带 `Content-Type: application/json`，文件上传使用 multipart 的 `file` 字段。不要在请求 URL 中携带令牌。

令牌来自运行应用根目录的 `data/story/api-token`，不是图片或音频服务的令牌，也不是旧版 APPDATA 目录。自定义 `--data-dir` 时使用实际目录。手机端 19879 不提供这套 Agent CRUD 接口。

`GET /v1/projects` 返回摘要数组（含 id、name、directory）；`GET /v1/projects/{pid}` 返回完整 Project。`POST /v1/projects/open` 返回完整 Project，**没有 project 包装**。局部修改与事务返回 `{revision, updated, ids, project}`，ids 按操作顺序排列。

## 新建与读取

| 请求 | 请求体／说明 |
| --- | --- |
| POST /v1/projects/open | `{name:"剧名",directory:"绝对项目目录"}`；directory 可省略使用默认设置。传 directory、不传 name 为打开已有项目。名称不可重复。 |
| GET /v1/projects/{pid}/content | 整剧内容；支持 chapter_id、episode_id、include_assets=false 查询参数。范围结果不能整部 PUT。 |
| GET /v1/skill | 应用内文字分镜 Skill；返回结构以实时接口为准。 |

新项目自动带一季一话；读取返回的 chapters 与 episodes 后改名或填入内容。不要假定其 ID。项目初始画幅1376×768、24fps。

## 修改与历史

单项创建／修改体：

```json
{"revision":0,"actor":"外部创作Agent","reason":"补充开场动作","data":{"script":"实际剧本正文"}}
```

| 请求 | data 对应类型 |
| --- | --- |
| POST /v1/projects/{pid}/chapters | Chapter |
| POST /v1/projects/{pid}/chapters/{cid}/episodes | Episode |
| POST /v1/projects/{pid}/episodes/{eid}/shots | Shot |
| POST /v1/projects/{pid}/assets | Asset |
| PATCH /v1/projects/{pid}/chapters/{cid} | Chapter 局部字段 |
| PATCH /v1/projects/{pid}/episodes/{eid} | Episode 局部字段 |
| PATCH /v1/projects/{pid}/shots/{sid} | Shot 局部字段 |
| PATCH /v1/projects/{pid}/assets/{aid} | Asset 局部字段 |

`POST /v1/projects/{pid}/transactions`：

```json
{
  "revision":2,"actor":"外部创作Agent","reason":"同步剧本和镜头",
  "operations":[
    {"action":"update","entity":"episode","id":"实际话ID","data":{"script":"修订正文"}},
    {"action":"create","entity":"shot","parent_id":"实际话ID","data":{"title":"回头","duration":5,"description":"人物回头望向门口。"}}
  ]
}
```

action 支持 create/update/delete；entity 支持 chapter/episode/shot/asset/project。episode 创建 parent_id 为章 ID，shot 创建 parent_id 为话 ID。资产和章无需 parent_id。ID 由服务产生，不在 data 中提交 id。project 只支持 update name、width、height、fps、style。一次1–200操作，验证失败全部不写入；多个依赖批次之间不构成一项大事务。

删除使用 transaction 的 delete 操作和真实 id；资产仍在 asset_ids 中被引用时拒绝删除，先更新相关镜头的正文与 asset_ids。数组替换会覆盖旧数组。普通编辑优先实体 PATCH，不使用整部 PUT。

`GET /v1/projects/{pid}/history` 获取历史；`GET /history/{version}` 读取列表返回的八位历史 ID；`POST /history/{version}/restore` 请求 `{revision:当前版本}`。恢复创建新版本。以上 history 路径均以 `/v1/projects/{pid}` 为前缀。无实际内容变化不会增加历史。

## 数据字段

- Chapter：title、episodes。通常用子实体接口追加话，避免整体覆盖 episodes。
- Episode：title、kind（episode／special）、script（Markdown纯文本）、shots（有序数组）。导入脚本文字不自动生成结构化 shots。
- Shot：title、scene、description、duration、shot_size、angle、camera_move、lighting、speaker、dialogue、delivery、emotion、sound、subtitle、asset_ids、disabled。可省略的文本默认空；景别默认中景，角度平视，运镜固定，duration 默认5秒。
- duration 是秒数，可为小数，范围 `(0,3600]`；没有 frames 字段。“秒＋帧”转换为 `秒+帧/fps`，例如24fps的5秒12帧是5.5。
- Asset：tags 为手动标签字符串数组，默认空，更新时替换整个数组；支持在资产库及 @ 选择器中搜索。rating 为0–5整数，0表示未评分，默认0；name 必填，kind 为 character／scene／prop／other；deprecated 为是否弃用，默认 false，弃用保留已有引用；description、gender、body、form、clothing、constraints 为设定文字；image 为参考图，voice 为参考音频；voice_description、voice_preset（默认vivian）、voice_reference_text 配置声音；generation_prompt 保存已知设定图提示词。
- Shot 媒体：image（封面）、images、hidden_images、audio、audio_text、audio_duration。普通文字创作不填造假路径；已有媒体字段应保留。镜头描述更改不会证明旧图仍适用，需在交付中标明是否需要重新生成。
- Project：width／height 为256–2048且32的倍数，总像素不超2,097,152；fps 为1–120整数；style 为全剧视觉风格。全项目所有 ID 唯一。

## 素材、图片与声音（仅在用户要求时）

1. `POST /v1/projects/{pid}/media` 上传 file，读取返回 path、metadata 和 warning。把 path PATCH 到资产 image／voice 或目标镜头。路径格式为 `media/<真实32位ID>.<扩展名>`，不能填本地绝对路径或编造文件名。上传本身不等于绑定。
2. 通过 `@[显示名](asset:实际ID)` 在 description 引用，并把该 ID 加入 asset_ids。即使仅作环境参考、未写在正文，也可保留真实场景 asset_ids。
3. `POST /v1/projects/{pid}/generation-preview`，请求 `{kind:"shot",target_id:镜头ID,revision:当前版本}`。board 需 kind=board、target_id=话ID、shot_ids 最多9个真实镜头ID。检查响应 prompt、references、warnings 和 revision；生图尺寸受应用最大边设置限制。
4. `POST /v1/projects/{pid}/generate` 使用同样目标与 revision；可传 prompt 作为补充说明，或 prompt_override 使用检查后的完整正文（不重复添加服务模式前缀）。kind=asset 时 target_id 为资产 ID。board 生成一张多格总览，不是多张单镜效果图。
5. `POST /v1/projects/{pid}/speech` 请求 `{shot_id:镜头ID,revision:当前版本,use_reference:true}`。只朗读 dialogue，speaker 精确匹配角色；参考克隆需要真实 voice 和准确 voice_reference_text。也可 use_reference=false 用预设。
6. 生成返回任务记录；以实际返回 id 查询 `GET /v1/projects/{pid}/jobs/{jid}`，轮询间隔建议2–5秒。失败报告原因，不无限重试。完成后读取最新项目，再 `POST /jobs/{jid}/apply`，请求 `{revision:当前版本}`，让服务绑定并创建历史；生成完成不等于已应用。取消用 `POST /jobs/{jid}/cancel`。这些路径均带项目前缀。
7. 配音不自动改变镜头时长；比较 audio_duration，必要时在用户要求范围内调整。对白变化后旧 audio_text 不匹配，旧配音不能当作最新结果。

PNG 元数据由项目接口按支持范围处理；JPEG/WebP 当前不解析或重写 XMP。不把 warning 当作已完成保证，不臆造旧图片原始提示词。读取图片元数据只取描述性信息。

## 导入、外部文字模型与导出

- `POST /v1/import-script` 上传 .md/.markdown/.txt，只返回解析章节，不保存；将所需正文和结构通过创建或事务接口写入，勿将解析 ID 当成已存在实体。
- `POST /v1/projects/{pid}/agent` 请求 `{mode:"rewrite"或"shots",content:"正文",instruction:"要求"}`，分别返回 text 或 shots 提案。逐项检查后保存；create shot 的 data 中删除提案 id，不直接传入服务创建接口。
- `GET /v1/projects/{pid}/export/{eid}?group=true` 返回 ZIP；false 为一镜一 Clip。导出需要媒体等满足校验，不能保证无素材的文字提案可直接渲染。

## 错误与重试

401：确认应用对应令牌，不打印密钥。404：重新查询 ID，不能凭空补 ID。409：检查响应是否版本冲突、名称／目录冲突或仍有引用，分别处理。422：按错误修正字段、引用或时长。连接失败：报告服务未可达，不直接操作存储替代。写入超时先回读核对，无法确认时保留待执行操作，避免重复追加。仅在用户要求配置时读取／更改 settings，禁止把其中服务密钥发给模型。


## 角色技能

Asset 的 `skills` 数组保存角色技能，默认空。每项包含 `id`（稳定ID，新增时可省略由服务生成）、`name`（1–200字）、`description`、`video_prompt`（动画描述）、`rating`（0–5整数，0为未评分）。界面按星级降序展示。通过资产 PATCH 更新整个 skills 数组，修改已有项时保留ID和其他技能；删除后仍可从历史恢复。不同技能ID不得重复。动画描述供视频创作引用，当前不会自动注入所有镜头的生图或视频提示词。
