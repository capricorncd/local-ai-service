# Local AI Image

[中文文档](README.zh-CN.md) · [HTTP API](docs/API.md)

A separate Tauri v2 image editor with a Photoshop-inspired canvas, layer panel, masks and local Qwen Image 2.1 inference. It does not require an external ComfyUI service. It embeds a pinned ComfyUI **inference library**, without loading custom nodes or starting its web server.

## Start

From the repository root on Windows:

```powershell
powershell -ExecutionPolicy Bypass -File apps/image/scripts/setup.ps1
npm install
npm run image:tauri -- dev
```

The app starts its API at `127.0.0.1:19877`. Model loading happens only for generation; the inference process exits after each task to release GPU memory. One shared Python environment under `runtimes/image` handles all image operations. Audio dependencies are unchanged.

Select the model directory or individual main model, VAE and encoder files in Settings, then save. No personal model directory is preconfigured. Absolute file paths may point to different directories. Existing saved settings are preserved. Required files:

- `qwen_image_2.1_bf16.safetensors`
- `qwen_image_2.1_vae_bf16.safetensors`
- `qwen3vl_8b_bf16.safetensors`

The two `qwen3.5_9b_*_pe_*` prompt-enhancement weights are optional and are **not used by this first adapter**. No model weights are duplicated or automatically downloaded.

## Editing and projects

Import PNG/JPEG/WebP images as layers. Move, resize, reorder, rename, duplicate, hide and lock layers; adjust opacity and choose which layers participate in inference. Enabled visible layers are sent bottom-to-top as numbered references, each rendered onto the canvas with its position, scale and opacity. The first reference is the base for masked editing. Use a single base layer when editing a selection.

The brush and ellipse tools create masks. White edits and black preserves. A separate mask must match the canvas dimensions. Outside-mask preservation is composited from the first reference after inference. Masked output uses the first reference's dimensions.

Eleven operation presets cover text generation, continued editing, transparent PNG, subject extraction, panorama, fidelity, brush/ellipse/mask editing, transparent editing and multiple references. Presets supply model instructions; panorama seams and identity fidelity remain model-dependent. Transparency comes from the model's RGBA output, not background-color removal.

Export `.laimage` projects to keep original embedded image bytes, layers, visibility, reference selection, canvas, masks, prompts and parameters. Import to resume. This is an app-native JSON format, not PSD. Undo/redo history and generated-job thumbnails are not embedded. Edits automatically save after a 1.5-second pause and before normal window close. Startup restores the most recent state; Recent records lets you open any of the latest 30 complete snapshots. Shared image data is deduplicated. Force quit/power loss may lose changes that have not yet been saved. Exported projects may contain large embedded images (200 MB maximum import).

Results can be added as new layers and downloaded as PNG. The PNG contains `ImageAssetMetadata` with the exact submitted prompt, reference IDs, model names and generation parameters.

## Limits and validation

Output area is at most 2 megapixels; references: 10; layers: 50; uploads: 32 MB / 20 megapixels. Generation is queued serially. Cancellation terminates the dedicated inference process. Jobs and configurations persist in the image app's own data directory (`studio.local-ai.image`), separate from audio (`studio.local-ai.manager`).

API contract tests run without loading models. Actual inference and GPU performance require a configured runtime and enough free RAM/VRAM. The application currently uses Chinese UI text; the audio app retains its existing Chinese/English/Japanese localization.

## Third-party licensing

Application terms are in the root LICENSE. ComfyUI inference code is GPL-3.0; Qwen Image 2.1 uses its own research license. Their terms remain applicable; this workspace's license does not relicense them. Check redistribution compatibility before bundling third-party code or weights.
