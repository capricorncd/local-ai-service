# 从零创建一段故事的 Python 示例

使用 Python 和 requests。设置 `STORY_APP_ROOT` 为应用根目录，`STORY_PROJECT_DIR` 为用户选择的**新项目绝对目录**，`STORY_PROJECT_NAME` 为新的剧名。例子创建短开场片段，并非完整1–3分钟一集。运行会真实写入；不要将它作为生产数据上的探活测试，也不要在请求超时后整段重跑。

```python
import os
from pathlib import Path
import requests

base = "http://127.0.0.1:19878"
token = (Path(os.environ["STORY_APP_ROOT"]) / "data/story/api-token").read_text().strip()
session = requests.Session()
session.headers["Authorization"] = "Bearer " + token

def call(method, path, **kwargs):
    response = session.request(method, base + path, timeout=30, **kwargs)
    response.raise_for_status()  # 冲突/超时交由调用者回读处理，不自动重试写入
    return response.json()

project = call("POST", "/v1/projects/open", json={
    "name": os.environ["STORY_PROJECT_NAME"],
    "directory": str(Path(os.environ["STORY_PROJECT_DIR"]).resolve()),
})
pid = project["id"]
cid = project["chapters"][0]["id"]
eid = project["chapters"][0]["episodes"][0]["id"]

def transaction(reason, operations):
    global project
    result = call("POST", f"/v1/projects/{pid}/transactions", json={
        "revision": project["revision"], "actor": "StoryAgent",
        "reason": reason, "operations": operations,
    })
    project = result["project"]
    return result["ids"]

character, scene = transaction("建立开场角色与场景", [
    {"action": "create", "entity": "asset", "data": {
        "name": "陈墨", "kind": "character", "gender": "男",
        "description": "短黑发的年轻男子，灰色外套，右手持黑色手电筒。",
        "clothing": "灰色外套、深色长裤", "constraints": "保持短黑发与灰色外套一致。"}},
    {"action": "create", "entity": "asset", "data": {
        "name": "废弃仓库", "kind": "scene",
        "description": "狭窄仓库，生锈铁门，纸箱沿右侧墙壁堆叠，水泥地面。"}},
])
mention = f"@[陈墨](asset:{character})"
script = """1-1 废弃仓库 [内] [夜]
镜1（全景 / 平视 / 缓慢推进）3秒
△ 陈墨推开铁门，手电光扫过右侧纸箱。
【音效】雨声，铁门摩擦声。
镜2（近景 / 平视 / 固定）4秒
△ 陈墨停步，攥紧手电筒。
陈墨（低声）：这地方不对劲。
"""
ids = transaction("保存第1话开场剧本与两镜分镜", [
    {"action": "update", "entity": "episode", "id": eid,
     "data": {"title": "第1话 雨夜来客", "script": script}},
    {"action": "create", "entity": "shot", "parent_id": eid, "data": {
        "title": "推门", "scene": "1-1 废弃仓库 [内] [夜]",
        "description": mention + "推开铁门，手电光扫过右侧纸箱。",
        "duration": 3, "shot_size": "全景", "angle": "平视",
        "camera_move": "缓慢推进", "lighting": "手电冷光，门外微弱夜光",
        "sound": "雨声，铁门摩擦声", "asset_ids": [character, scene]}},
    {"action": "create", "entity": "shot", "parent_id": eid, "data": {
        "title": "警觉", "scene": "1-1 废弃仓库 [内] [夜]",
        "description": mention + "停步，攥紧手电筒。",
        "duration": 4, "shot_size": "近景", "angle": "平视", "camera_move": "固定",
        "speaker": "陈墨", "dialogue": "这地方不对劲。", "emotion": "低声",
        "delivery": "口型同步", "asset_ids": [character, scene]}},
])
verified = call("GET", f"/v1/projects/{pid}")
episode = next(e for c in verified["chapters"] for e in c["episodes"] if e["id"] == eid)
assert episode["script"] == script
assert [s["id"] for s in episode["shots"]] == ids[1:]
assert all(set(s["asset_ids"]) <= {a["id"] for a in verified["assets"]} for s in episode["shots"])
history = call("GET", f"/v1/projects/{pid}/history")
assert history
print({"project_id": pid, "episode_id": eid, "revision": verified["revision"],
       "shots": len(episode["shots"]), "duration": sum(s["duration"] for s in episode["shots"])})
```

示例未上传或生成图片，因此镜头效果图为空是正确结果。继续添加季／话时，先读取最新 revision，再调用创建接口；不要重复运行新建故事部分。
