# Image API

Base URL: `http://127.0.0.1:19877`. Every `/v1/*` request requires `Authorization: Bearer <token>`. Read the token from the image app data directory's `api-token` file; do not use the audio app token. Tauri data directory on Windows: `%APPDATA%\studio.local-ai.image`. Browser development may use a separately chosen `--data-dir`.

Interactive schema: `/docs`; machine-readable schema: `/openapi.json`. Bind is loopback only. Requests are limited to 200 MB. The API never accepts a caller-selected output path.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Lightweight health check (no auth, no GPU loading) |
| GET / PUT | `/v1/config` | Read/write model directory, filenames, worker Python and inference core directory |
| POST | `/v1/images` | Multipart `file` upload; returns `{id,width,height,name}` |
| GET | `/v1/images/{id}` | Authenticated reference image download |
| POST | `/v1/jobs` | Submit generation/edit job; returns 202 and persisted job |
| GET | `/v1/jobs` | Latest 100 jobs, status, progress, error, parameters, file location |
| GET | `/v1/jobs/{id}` | Poll one job |
| POST | `/v1/jobs/{id}/cancel` | Cancel queued/running task |
| GET | `/v1/jobs/{id}/image` | Download completed PNG |
| POST | `/v1/jobs/{id}/reference` | Copy generated result into a new reference, return its ID |
| POST | `/v1/projects` | Import/save `.laimage` JSON; returns project ID |
| PUT | `/v1/projects/{id}` | Update an existing project |
| GET | `/v1/projects` | List saved projects |
| GET | `/v1/projects/{id}` | Download project JSON as `.laimage` |
| POST | `/v1/projects/{id}/generate` | Render enabled visible project layers and submit using the project's prompt and parameters |
| GET | `/v1/recents` | List the latest 30 operation snapshots (summary only, newest first) |
| POST | `/v1/recents` | Save a complete project snapshot; consecutive identical saves are deduplicated |
| GET | `/v1/recents/{id}` | Restore the full project, including original layer images and mask |

## Generation

```json
{
  "mode": "text",
  "prompt": "A watercolor mountain village at dawn",
  "negative": "",
  "references": [],
  "mask": null,
  "width": 1024,
  "height": 1024,
  "steps": 30,
  "cfg": 4,
  "seed": -1
}
```

`mode`: `text`, `continue`, `transparent`, `extract`, `panorama`, `fidelity`, `brush`, `circle`, `mask`, `alpha`, `multi`.

All modes except text/transparent/panorama require at least one uploaded reference ID; multi requires two. At most ten references. Brush/circle/mask require a separate uploaded mask ID with the same dimensions as reference 1 and at least one non-black pixel. White means edit. To edit a generated result, first call its `/reference` endpoint, then include the returned ID in `references`.

Width and height are multiples of 32, between 256 and 2048, with a total area at most 2,097,152 pixels. For image editing, reference 1's aspect ratio is retained while using the requested pixel area; masked output is restored to reference 1's size. Steps: 1–80; CFG: 1–10; seed: -1 (random) or unsigned 32-bit integer. The actual random seed is persisted in the returned job.

Statuses: `queued`, `running`, `completed`, `failed`, `cancelled`. Models and runtime must be configured; otherwise submission returns 409. Invalid requests return 422. Startup marks interrupted jobs failed. Use GET jobs to poll; inference does not block health, playback in the separate audio app, or cancellation.

## Projects

The editor automatically saves after approximately 1.5 seconds without edits and before a normal desktop-window close. On startup it restores the latest snapshot unless the user has already started editing. “最近记录” opens any of the latest 30 snapshots. Images shared between snapshots are stored once; expired snapshots and unused image payloads are pruned transactionally. A force kill or power loss can lose edits not yet saved. API snapshot requests use the same project schema below.

Project JSON contains `format: "local-ai-image"`, `version: 1`, `name`, `width`, `height`, `layers`, `active`, `mask`, `prompt`, `negative`, `mode`, `steps`, `cfg`, `seed`.

Each layer has `id`, `name`, `source` (PNG/JPEG/WebP base64 data URL), original `width`/`height`, `x`/`y`, `scale`, `opacity` (0–1), `visible`, `locked`, `reference`. Layers are bottom-to-top. `active` is the selected layer ID or null. `mask` is an embedded image data URL or null. The same JSON is accepted by the app's project importer. Saving a project does not run inference. Call `/v1/projects/{id}/generate` to submit its enabled visible layers, or submit independently rendered images through `/v1/images` then `/v1/jobs`.
