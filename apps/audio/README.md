# Local AI Service

English | [中文文档](README.zh-CN.md)

A Windows desktop manager for local AI audio services, built with **Tauri v2, Rust, React and Lucide**. Rust manages the window and process tree, a lightweight Python API serves HTTP requests, and model inference runs in app-owned Python environments. Model code is not imported into the API process.

## Features

| Service | Model / implementation | Capabilities |
| --- | --- | --- |
| Music generation | YuE2 | Lyrics and style to songs, optional LoRA, score export and desktop score editing |
| Audio denoising | MossFormer2_SE_48K | Speech enhancement for audio or video |
| Speech separation | MossFormer2_SS_16K | Separate two overlapping speakers |
| Sound generation | MOSS-SoundEffect v2.0 | Generate sound effects from Chinese or English descriptions |
| Text to speech | Qwen3-TTS / Breeze TTS 2 | Shared API with selectable model, presets and reference voices as supported |
| Voice conversion | Seed-VC | Preserve spoken content while changing the voice |
| Audio editing | AuK | Instruction-based speech editing, enhancement and extraction |
| Sound library | Local folders + SQLite | Index, categorize, search, preview and download sound files |

The interface supports **English, Simplified Chinese and Japanese**. It follows the system language by default. Change it in **Settings → Interface language**; preferences are saved and apply immediately. See [i18n documentation](docs/i18n.md) (Chinese).

## Use with ComfyUI-Capricorncd-Timeline

Use Local AI Service alongside [ComfyUI-Capricorncd-Timeline](https://github.com/capricorncd/ComfyUI-Capricorncd-Timeline) for **audio cleanup and repair in AI-generated videos, and BGM creation**. Timeline handles shot generation, editing and composition; this app provides local audio processing and generation.

- **Video audio repair:** load a generated video's audio or the video itself for speech denoising, or use AuK to edit supported speech clips. Preview results before replacing the original audio; processing quality depends on the source and model.
- **BGM creation:** describe the scene, mood, instruments and style to generate background music. For instrumental intent, use `[Instrumental]` as lyrics and specify no vocals in the style. This is prompt guidance, not a guaranteed vocal-free mode; when needed, use song separation to obtain an instrumental track and check for residual vocals.
- **Sound design:** generate environmental or action effects with MOSS-SoundEffect, or find existing effects in the local sound library.

A practical workflow is to generate video clips in Timeline, process or create audio in this app, download the results, and import them into Timeline's audio tracks for alignment, volume adjustment and final composition. Mute the original audio where you replace it to avoid duplicate playback.

This describes a file-based workflow. Direct API integration requires matching Timeline's service contracts; this documentation does not imply a built-in one-click connection.

## Run

Double-click **`Local-AI-Service.exe`** in the project root. Keep `server/` and `runtimes/` beside it. The prepared local development delivery includes dedicated interpreters, GPU libraries, FFmpeg and MossFormer2 weights; a fresh source checkout requires runtime and model setup.

- The app starts the API at `http://127.0.0.1:19876` and checks each service's configuration.
- Each service has its own model paths, output paths and parameters. Missing models, directories or runtimes leave that service in **Setup required** without preventing other services from working.
- Save configuration changes, then manually restart the relevant service. Saving does not switch a running model automatically.
- For the sound library, choose a root folder, save, restart the service and scan. Subfolder paths become categories.
- Select the YuE2 model file in the music service settings. Select the SheetSage2 encoder for audio reference or Cover transcription. Configure these paths before first use; existing ComfyUI model files can be reused. Save and restart the music service.
- Default denoising and speech separation models are under `runtimes/models/MossFormer2_SE_48K` and `runtimes/models/MossFormer2_SS_16K`.
- View or copy the API key on the **API access** page. The server listens on loopback only, and business endpoints require Bearer authentication.
- Configuration, SQLite databases, logs and results default to `%APPDATA%\studio.local-ai.manager`. Settings shows the actual location.
- Closing the desktop app stops the services. A Windows Job Object terminates the API, inference workers and FFmpeg children. Unfinished jobs are marked as interrupted failures on the next startup; they are not automatically retried.

This is a Windows development delivery with local dependency folders, not a single-file installer. Virtual environments contain absolute paths. After moving the folder or switching computers, rebuild runtimes at the new location and update the API Python, model and output paths.

## GPU and memory

**Starting the app does not load AI models or allocate GPU memory for them.** The API uses a small amount of CPU/RAM; the WebView may use graphics resources for rendering. A worker loads a model only when a job runs.

AI jobs share a serial queue with a capacity of 32. Each job releases its process and model resources after completion, failure, cancellation or timeout. Idle models therefore do not remain in VRAM, at the cost of loading weights for each job. Two songs in one job reuse the model and run sequentially with seeds `seed` and `seed + 1`.

The app does not manage other applications' GPU usage. Heavy usage elsewhere can still cause inference to fail. Sound library queries do not require a GPU.

YuE2 uses a Comfy-Org merged checkpoint containing the language/generation model and audio VAE. Text-to-song generation does not load SheetSage2; desktop audio-reference workflows use it separately. The duration setting is an upper limit and may truncate a song. Denoising extracts the first audio track from video and rejects inputs over the configured limit rather than silently truncating them.

## HTTP API

Machine-readable specification: `GET /openapi.json`. Interactive FastAPI documentation: `/docs` (Swagger UI assets require network access). Business endpoints require `Authorization: Bearer <API_KEY>`; `/health` is the unauthenticated exception.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | Liveness check, not model readiness |
| GET | `/v1/status` | Service states, configuration errors, restart flags and current job |
| GET / PUT | `/v1/config` | Read / save configuration; saving does not hot-reload models |
| POST | `/v1/services/{service}/restart` | Recheck and apply configuration; unfinished jobs can cause HTTP 409 |
| GET | `/v1/voices` | Voice presets and preview URLs |
| GET | `/v1/voices/{id}/audio` | Preview a voice preset |
| GET | `/v1/tts/models` | TTS model capabilities, readiness and download status |
| POST | `/v1/tts/generate` | Text to speech with model selection |
| POST | `/v1/voice/convert` | Convert source audio to a preset or reference voice |
| POST | `/v1/sfx/generate` | Generate WAV sound effects from Chinese or English descriptions |
| POST | `/v1/music/generate` | Generate songs from lyrics, style and optional parameters |
| POST | `/v1/uploads` | Upload multipart `file` audio/video; returns `upload_id`; maximum 512 MB |
| POST | `/v1/denoise` | Denoise an uploaded file using JSON `{"upload_id":"…"}` |
| POST | `/v1/denoise/file` | Direct multipart upload; optional `segment_seconds`, `max_duration` |
| POST | `/v1/separate` | Separate two speakers using JSON `{"upload_id":"…"}` |
| POST | `/v1/separate/file` | Direct multipart separation upload with optional duration/segment parameters |
| GET | `/v1/jobs` / `/v1/jobs/{id}` | Latest 200 jobs / a specific job |
| DELETE | `/v1/jobs/{id}` | Cancel a queued or running job |
| GET | `/v1/jobs/{id}/files/{index}` | Download a generated file |
| GET | `/v1/jobs/{id}/scores/{index}` | Read an exported score; add `?download=true` for ABC download |
| GET | `/v1/sounds?category=nature&q=rain&limit=50&offset=0` | Filter by category/name with pagination |
| GET | `/v1/categories` | Categories and file counts |
| POST | `/v1/sounds/scan` | Atomically rebuild the current root's index without changing audio files |
| GET | `/v1/sounds/{id}/audio` | Play or download audio with HTTP Range support |
| GET | `/v1/logs` | Latest 200 service log lines |

### Music generation example

```json
{
  "lyrics": "[Verse]\nEvening breezes pass my window\n[Chorus]\nTurn these thoughts into a song",
  "style": "English, indie pop, acoustic guitar, warm female vocal",
  "count": 2,
  "seed": 42,
  "mode": "full",
  "steps": 32,
  "cfg": 1.0,
  "max_duration": 360
}
```

Omitting `count` uses the service default of one or two songs. `mode` accepts `full`, `melody` or `off`. Additional parameters include `temperature`, `top_p`, `top_k` and `repetition_penalty`; see OpenAPI for ranges.

By default, requests wait for completion and return `{id,status,files:[{url,path,seed,sample_rate,duration}],…}`. For long jobs, use `?wait=false`: the API returns HTTP 202 and a job immediately. Poll `/v1/jobs/{id}`, then download from `result.files[].url`. Downloads require authentication. Disconnecting a synchronous client does not cancel a submitted job; use DELETE. Asynchronous submission returns 429 for a full queue, 503 for a model that is not ready, and 422 for invalid parameters.

Python client example (the caller manages its own Python environment):

```python
import requests
import time

s = requests.Session()
s.headers['Authorization'] = 'Bearer YOUR_API_KEY'
base = 'http://127.0.0.1:19876'
r = s.post(base + '/v1/music/generate?wait=false', json={
    'lyrics': '[Verse]\nHello world', 'style': 'acoustic pop', 'count': 1,
})
r.raise_for_status()
job = r.json()
while job['status'] in ('queued', 'running'):
    time.sleep(2)
    r = s.get(base + '/v1/jobs/' + job['id'])
    r.raise_for_status()
    job = r.json()
if job['status'] != 'succeeded':
    raise RuntimeError(job.get('error'))
for i, item in enumerate(job['result']['files']):
    audio = s.get(base + item['url'])
    audio.raise_for_status()
    with open(f'song-{i + 1}.wav', 'wb') as output:
        output.write(audio.content)
```

For denoising, upload first and submit the returned `upload_id`, or use the direct file endpoint. Remote URLs and arbitrary local input paths are not accepted. Uploaded originals, results and `worker.log` are retained for inspection; periodically remove unwanted files. Automatic retention periods are not implemented.

## Music workspace

Expand **Creative presets and styles** for accompaniment rearrangement, a manually specified source BPM, full-song development, reference-style arrangements, male/female vocals and instrumental BGM. Twelve style buttons include Chinese traditional-inspired, playful Chinese fantasy, pop, rock, folk, electronic dance, jazz, easy listening, cinematic, Lo-fi, ambient and anime pop. Buttons fill editable prompts without submitting a job. Target minutes are sent as `max_duration` in seconds; this is a cap, not a guaranteed length or continuation. BPM and vocal preferences are prompt guidance, not precise controls.

Blank lyrics default to `[Instrumental]` with no-vocal guidance. Blank style does not force a genre, with or without references: no random style or source style is automatically filled in. Only no-vocal guidance is added when lyrics are blank. This lets the model choose, but does not imply automatic genre recognition or faithful style matching. See [preset behavior and research sources](docs/music-presets.md) (Chinese).

### LoRA

Optional **speedyrulz / Starnodes2024 LoRA** support is disabled by default. Select native ComfyUI `.safetensors` files and configure acoustic/planner weights through the app or supported API parameters. The integration loads trained LoRA files; it does not provide training. See [YuE2 LoRA documentation](docs/music-lora.md) (Chinese).

### Scores

`POST /v1/music/generate` accepts `generate_score`, defaulting to `false`:

```json
{"lyrics":"[Verse]\nEvening breezes pass my window", "style":"English pop", "mode":"full", "generate_score":true}
```

Each song can include an ABC score. `full` exports melody/chord planning; `melody` exports melody planning. `mode=off` with `generate_score=true` returns 422. Disabling export does not change planning or audio generation.

Synchronous responses contain `scores`; completed asynchronous jobs contain `result.scores`. Entries include `audio_index` (zero-based index into `files`), `format: "abc"`, `mode`, `path` and `url`. When export is disabled, the array is empty. The score endpoint returns ABC source and metadata as JSON; add `?download=true` to download ABC. Both require authentication; missing files or invalid indices return 404.

The music page displays notation and ABC using bundled abcjs. Older jobs are not retroactively exported. Nonstandard notation may not render correctly, but the source remains available. These are planning scores, not full ensemble transcriptions of the final recording, and may differ from the final performance.

The desktop editor supports ABC edits, previews and regeneration while keeping the original. It generates one new song with the original parameters and corresponding seed, bypasses the planner, removes planner LoRA and retains acoustic LoRA. **Score editing is desktop-only:** the public music API rejects `abc` with 422. Internal routes require separate desktop credentials and are excluded from OpenAPI.

### Titles, groups and variations

The song panel opens at **Workspaces > Ungrouped**. Click **Workspaces** to view/search workspaces; the first entry creates a workspace, including an empty one saved in SQLite. Existing groups appear as workspaces. New songs and score regenerations are assigned to the currently open workspace; generation from the workspace list or Ungrouped goes to Ungrouped. Use More → Move to to move existing tracks between workspaces, including Ungrouped. Click the pencil beside a song title to rename it inline (Enter or checkmark saves; Esc or × cancels). Workspace counts and song lists currently cover the latest 200 jobs.

Completed tracks support independent 1–5 star ratings and favorites, saved in SQLite. Click the currently selected star again to clear its rating. The compact toolbar searches song titles and styles within the current workspace; its Filters popover shows the active condition count and supports resetting filters. Search covers the loaded tracks from the latest 200 jobs. Within a workspace, combine an exact star rating, Favorites only, and track type tags. No selected star means all ratings; clicking the selected star clears that filter. Track type tags also toggle off to show all types. Use these controls to filter the list. Original songs and separated stems can be annotated independently.

Form drafts are saved locally as you edit and restored on reopening, including the last page/workspace, generation text, options and reference audio/video (cached in IndexedDB). Removing a reference also removes its cached draft. Drafts do not submit jobs automatically or apply unsaved service configuration. Desktop and browser drafts are separate; clearing application/browser storage removes them. Large media may fail to cache if local storage is full.

Optional `title` accepts up to 120 characters. Blank titles use local submission time in `yyyyMMdd-hhmmss_n` format (24-hour clock, numbering from 1). A supplied title is used directly for one song; two receive `_1` and `_2`. Song and score results include titles. Invalid Windows filename characters become underscores, and separate job directories prevent same-title collisions.

The song list shows generating/completed songs and playback/download controls. Rename individual songs, create or assign groups, clear a group, and filter by group or track type. Metadata is stored in SQLite and can be edited while queued or running without being overwritten on completion. Original files and download URLs remain intact; app downloads use the updated title. The list covers the latest 200 jobs.

- **Cover:** extract melody without chords using SheetSage2, then generate with new lyrics/style.
- **Remix:** extract melody and chords for a new arrangement; this is not a multitrack mixing console.
- **Edit score:** edit saved ABC notes, rhythm, key and chords, with optional lyric/style changes.
- **Edit lyrics:** reuse the saved score or transcribe source audio. This regenerates the whole song, not just selected words or segments.
- **Reuse parameters:** restore title, lyrics, style, seed and options without referencing original audio or score.

Reference generation skips planner LoRA but supports acoustic LoRA. SheetSage2 transcription and YuE2 generation run sequentially and release models afterward. Missing SheetSage2 does not affect ordinary text-to-song generation. Transcription can be inaccurate and does not preserve the original voice. Version relationships use `source_job_id` and `source_audio_index`.

These variation operations are desktop-only. The public music API does not accept reference audio or ABC. Local segment replacement, song continuation, multitrack mixing and voice Personas are not currently provided.

### Reference audio

Drag audio or video onto the music page or click to upload. Formats include WAV, MP3, FLAC, OGG, M4A, AAC, OPUS, MP4, MOV, MKV, WEBM and AVI, up to 512 MB and 15 minutes. Music references, Qwen/Breeze voice references, voice-conversion references and AuK inputs share the audio/video picker. Video references are uploaded for automatic audio-only preview: the backend extracts the first audio track, previews up to 30 seconds as WAV, and displays no video. Generation uses the original upload with each model's existing duration limits, not the preview clip. Missing or undecodable audio produces an error. Preview requires configured FFmpeg but does not load AI models. The authenticated `POST /v1/uploads/{upload_id}/audio-preview?service=music` endpoint also accepts `tts`, `vc` or `auk`; it returns `audio_base64` containing the preview WAV. Temporary preview files are removed after encoding.

Choose melody-only or full planning to extract melody or melody/chords and regenerate with your lyrics/style. This does not recognize lyrics, copy the original voice or extend the original song. It uses SheetSage2 and the configured music FFmpeg. Direct generation and planner LoRA cannot be combined with reference audio. The desktop route is `/internal/music/reference`, not a public API.

### Vocal and instrumental separation

Click the separation button on an original song to queue separation. Two **44.1 kHz stereo WAV** tracks appear when complete: vocals and instrumental, retaining source relationships and groups. Both support renaming, grouping, preview and download. Duplicate pending requests for the same song are prevented.

This uses official TorchAudio HDemucs in the music Python environment without loading YuE2. The default weights are `runtimes/models/HDemucs/hdemucs_high_trained.pt`; if missing, the default file is downloaded from PyTorch on first separation. Processing uses overlapping chunks and releases the model afterward. Residual vocals or accompaniment may remain; this is not lossless separation and differs from MossFormer2's two-speaker separation.

## Text to speech and voice conversion

Qwen3-TTS and Seed-VC provide **nine selectable, previewable voice presets**, plus reference recordings where supported. Use the Text to speech and Voice conversion pages or their APIs.

- `GET /v1/voices`: presets, names, descriptions and preview URLs.
- `POST /v1/tts/generate`: text plus a preset/reference voice to speech. Select `qwen3-tts` or `breeze-tts2` using `model`.
- `POST /v1/voice/convert`: source audio plus a preset/reference voice to converted audio.

Qwen and Breeze share the TTS runtime. Breeze includes an explicit model-download button; model paths must be ready before inference. Capabilities and licensing differ. See [voice API and setup](docs/voice-api.md) and [unified TTS API, Breeze downloads and shared runtime](docs/tts-api.md) (Chinese).

## Sound generation: MOSS-SoundEffect v2.0

Use `POST /v1/sfx/generate` with Bearer authentication. It waits by default; `?wait=false` returns HTTP 202 and a job for polling.

```json
{
  "prompt": "Rain gently falling on leaves, occasional distant birds, no music or speech.",
  "seconds": 10,
  "count": 1,
  "seed": 42,
  "num_inference_steps": 100,
  "cfg_scale": 4.0,
  "sigma_shift": 5.0,
  "negative_prompt": ""
}
```

| Parameter | Default | Range / meaning |
| --- | --- | --- |
| `prompt` | Required | Chinese or English description, 1–4000 characters after trimming |
| `seconds` | 10 | 1–30 seconds, output in 0.1-second increments |
| `count` | 1 | 1–4 results generated sequentially using one loaded model |
| `seed` | 42 | 0–4294967292; results use seed, seed+1, etc. |
| `num_inference_steps` | 100 | 1–200; fewer steps can be faster but may reduce quality |
| `cfg_scale` | 4 | 1–20; native prompt guidance scale |
| `sigma_shift` | 5 | Greater than 0 and at most 20; native sampling schedule shift |
| `negative_prompt` | Empty | Unwanted sounds, up to 4000 characters |

Omitted duration, count, steps, guidance or schedule shift use settings applied by the latest service restart. Default timeout: 1800 seconds. There is no source-audio blend or artificial strength parameter. Output is **48 kHz mono PCM16 WAV**, with `path`, `url`, `duration`, `sample_rate` and `seed` under `files` for synchronous success or `result.files` for asynchronous jobs.

Default output is `sfx/<job-id>/` under app data. To include results in the library, configure output beneath the library root, save and restart `sfx`, then scan after generation. Other directories are not automatically copied or scanned.

After preparing the base runtime, rebuild the environment with:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup-sfx.ps1 -DownloadModel
```

The script uses app-owned Python 3.12, `runtimes/sfx` and `requirements/sfx.lock.txt`. Runtime code is pinned to `934d6826b084c46a0d033402174d5f8ac4ed2519`; only the sound-effect package is installed. Windows disables TorchDynamo compilation by default and uses PyTorch CUDA without system Triton. Inference does not automatically download missing files: configure them and restart the service. Initial model download requires network access.

The default model directory is `runtimes/models/MOSS-SoundEffect-v2.0` and must contain the text encoder, tokenizer, generation model and VAE. Sources: [official model card](https://huggingface.co/OpenMOSS-Team/MOSS-SoundEffect-v2.0), labeled Apache-2.0, and [official runtime](https://github.com/OpenMOSS/MOSS-TTS/tree/main/moss_soundeffect_v2). This model is distinct from MossFormer2.

Recorded local validation includes an RTX 4090 run using a Chinese prompt, 10 steps and two 3-second results (seeds 42/43), plus a desktop HTTP run with default 10 seconds, 100 steps and one result. The local sample is `data/sfx-default-sample.wav`. These checks validate functionality and format, not subjective quality.

## Speech separation: two speakers

**MossFormer2_SS_16K** separates two overlapping speakers; **MossFormer2_SE_48K** enhances speech. This service does not separate song vocals/accompaniment or track people in video.

Choose audio or video on the Speech separation page. Video uses its first audio track. Results are two **16 kHz mono WAV** tracks labeled Speaker 1/2. Numbers are not identities and may differ between jobs or segments. Check long recordings by listening. The model has fixed two-speaker output and no speaker-count or strength control.

```json
{"upload_id":"ID returned by the upload endpoint", "segment_seconds":2, "max_duration":1800}
```

Submit to `/v1/separate?wait=false`, or send optional parameters as form fields with `file` to `/v1/separate/file?wait=false`. Both require Bearer authentication; omit `wait=false` for synchronous completion.

| Parameter | Default | Meaning |
| --- | --- | --- |
| `segment_seconds` | 2 seconds | Segmentation threshold, 2–120 seconds; the underlying window remains the model's 2 seconds, not a strength setting |
| `max_duration` | 1800 seconds | Input limit, 1–7200 seconds; longer inputs are rejected |
| `device` | cuda | Service configuration can select CPU |
| `timeout_seconds` | 1800 seconds | Service timeout, 30–14400 seconds |

Omitted parameters use service settings. Each result includes `speaker` (1 or 2), `url`, `sample_rate`, `duration` and `path`. Jobs share the serial queue and release the model process afterward. Missing separation weights do not affect denoising.

## Audio editing: AuK

AuK supports instruction-based speech and a cappella lyric editing, emotion/voice changes, enhancement and extraction. It requires configured weights and dependencies. See [AuK integration documentation](docs/auk.md) (Chinese).

## App-owned runtimes and development

`runtimes/python/` contains dedicated CPython 3.12.13. Environments under `runtimes/api`, `music`, `denoise`, `sfx`, `tts` and `vc` do not enable system site-packages. Qwen and Breeze share TTS; denoising and two-speaker separation share ClearVoice. Conflicting dependencies remain in separate app-owned environments. Versions are locked in `requirements/*.lock.txt`; FFmpeg is also app-owned.

Prepare the base runtime in PowerShell (initial downloads need network access, disk space and an NVIDIA driver):

```powershell
./scripts/setup-runtime.ps1 -FFmpegSource '<path-to-ffmpeg.exe>' -DownloadDenoiseModel -DownloadSeparationModel
npm ci
./scripts/build.ps1
```

Scripts install into `runtimes/`, not system Python. Supply a trusted static Windows FFmpeg build. CUDA PyTorch and its app-local caches require substantial space. A full ComfyUI HTTP server is unnecessary: inference modules load from the dedicated runtime without custom nodes. Normal inference disables automatic Hugging Face downloads; explicit download workflows and the documented HDemucs first-use download are separate.

- Desktop development: `npm run tauri dev`.
- Standalone API: `runtimes/api/Scripts/python.exe server/run.py`, using project `data/`.
- Frontend: `npm run dev`; enter the key from `data/api-token` in the browser.
- Do not run desktop and standalone APIs on the same port.
- Tests: `.venv/Scripts/python.exe -m pytest tests -q` after preparing the test environment.
- GPU checks: `scripts/smoke_api.py` needs prepared audio/video; `scripts/smoke_separation.py <short-audio-or-video>` checks real separation endpoints.
- Translation checks: `node scripts/check-i18n.mjs`.

### Recorded validation and limitations

Previous local checks covered TypeScript/Vite and Rust builds; authentication, save/restart behavior, failure recovery, cancellation, library scanning/downloads, HTTP Range and path containment; and short YuE2 generation on RTX 4090 with two downloadable songs per asynchronous job.

MossFormer2 checks covered 25-second segmented denoising and video upload/audio extraction/download. SS_16K checks covered segmented/non-segmented inference, JSON/multipart requests and two downloadable tracks, with SE_48K regression checks. These used synthetic media to verify workflows, not real overlapping-speech separation quality. Historical test counts in the Chinese development notes refer to those implementation stages, not the current suite size.

Short functional checks do not guarantee long-song quality, all media formats or low-VRAM performance.

### Windows launch context and history

Launching from Codex's MSIX environment can redirect Roaming app data into Codex's LocalCache; normal direct launches read regular user Roaming. On 2026-09-17, older jobs/audio were copied into the normal-launch history while preserving originals. Local pre-recovery SQLite snapshots are in `data/recovery-20260917-232115`. Fixed data-root migration is not complete. When managing from Codex, inspect the actual API/database through a normal Windows process context rather than mistaking redirected data for active data.

### Playback and downloads

Active audio buttons show animated bars and, where text is present, “Playing.” Pausing or ending restores the regular state; clicking the active track toggles pause/resume.

Songs and separated tracks that have no recorded playback show a blue dot beside the title. The dot clears only after audio actually starts in the app, not on download or a failed playback attempt. Playback state is stored per track in SQLite and survives renaming, regrouping and restarts. Older tracks without recorded history initially show the dot; playback in external players cannot be detected.

Desktop audio and score downloads use the native Save As dialog, write the original bytes and show the saved path. Cancelling creates no file. Browser previews retain browser download behavior.

Generated audio and score results in the Windows desktop app also have an **Open folder** button. It opens File Explorer and selects the original output file. This is available in the song list, job result details, AuK results and score panel. Missing or moved files show an error; browser previews do not expose this desktop action.

## Upstream projects and licensing

- [Tauri v2](https://v2.tauri.app/) / [Lucide React](https://lucide.dev/guide/react)
- [Comfy-Org YuE2 weights](https://huggingface.co/Comfy-Org/YuE2)
- [Pinned YuE2 inference node](https://github.com/Comfy-Org/ComfyUI/blob/7a0b5eede3f9721c8faab290689893f36edc6d66/comfy_extras/nodes_yue2.py)
- [ComfyUI-ClearerVoice-Studio reference nodes](https://github.com/freeyaers/ComfyUI-ClearerVoice-Studio)
- [ClearerVoice-Studio](https://github.com/modelscope/ClearerVoice-Studio)
- [MossFormer2_SE_48K](https://huggingface.co/alibabasglab/MossFormer2_SE_48K) / [MossFormer2_SS_16K](https://huggingface.co/alibabasglab/MossFormer2_SS_16K)

Models and runtimes retain upstream licenses; YuE2 weights are labeled CC-BY-NC-4.0. Redistributing ComfyUI, FFmpeg, Python or models requires preserving their notices and complying with their licenses. This project's learning/research license does not override third-party terms.

Desktop icons derive from deterministic repository SVGs, not AI generation. PNG/ICO assets include ImageAssetMetadata identifying the absence of an original AI prompt; metadata updates are backed up and checked to preserve pixel data.

## Further documentation

The detailed guides below are currently in Chinese:

- [中文文档 — full Chinese README and development notes](README.zh-CN.md)
- [YuE2 LoRA](docs/music-lora.md)
- [Voice conversion, presets and setup](docs/voice-api.md)
- [Unified Qwen / Breeze TTS API](docs/tts-api.md)
- [AuK audio editing](docs/auk.md)
- [Interface languages](docs/i18n.md)

The Separation page offers Two speakers (MossFormer2 SS 16K), Vocals + accompaniment (HDemucs via the music service), and Run both. Run both queues two jobs sequentially and produces four labeled tracks with individual playback controls in Jobs. Both services must be ready. HDemucs accepts up to 15 minutes and outputs stereo 44.1 kHz WAV; speaker separation outputs mono 16 kHz WAV.

### Separation API modes

`POST /v1/separate` accepts optional `mode`: `speakers` (default, two speakers), `music` (vocals + accompaniment), or `both` (two queued jobs / four tracks). `/v1/separate/file` accepts the same field as multipart form data. Bearer authentication is required.

```json
{"upload_id":"your-upload-id","mode":"both"}
```

With `?wait=false`, single modes return the existing job object; `both` returns HTTP 202 with `{ "mode": "both", "jobs": [...] }`. Poll each job ID via `/v1/jobs/{id}`. With `wait=true` (default), `both` waits for both tasks and returns `status`, `jobs` and a combined `files` list (four tracks on success). An unsuccessful task returns HTTP 500 with completed results retained. A partial submission error includes `status: "partial"` and accepted `jobs`.

`title` is optional and names music stems. `segment_seconds` and `max_duration` apply only to speaker separation; HDemucs uses its existing fixed chunking and 900-second limit. Music mode requires the music service; both requires both services. Models run sequentially through the shared queue.

Playback mode cycles from Play in order (no repeat, default) → Repeat one → Repeat list via the button left of Configure. The song queue follows the visible workspace/search/filter order when playback is started. Repeat list wraps to the first track; sequential playback stops at the end. The mode is saved locally; restarting does not automatically start playback.
