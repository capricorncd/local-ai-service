# Local AI Apps

[中文文档](README.zh-CN.md)

- [Audio application](apps/audio/README.md): local music and sound effect generation, text-to-speech, voice conversion, audio editing, denoising and vocal separation.
- [Image application](apps/image/README.md): layer editor, masks, portable projects and local Qwen Image 2.1 inference.
- [Image HTTP API](apps/image/docs/API.md): upload, generate/edit, projects and task management.
- [Story application](apps/story/README.zh-CN.md): scripts, chapters, assets, storyboards, dialogue audio, version history and Timeline packages.
- [Story Agent API](apps/story/docs/API.md): scoped reads, versioned CRUD and atomic transactions on port 19878.

## Create videos with ComfyUI

If your computer can run ComfyUI and the models you need locally, pair these apps with [ComfyUI-Capricorncd-Timeline](https://github.com/capricorncd/ComfyUI-Capricorncd-Timeline) to bring scripts, images, dialogue and music together in a video creation workflow.

Plan stories, characters and shots in the story app, prepare visual assets in the image app, and use the audio app to create dialogue, sound effects and background music or repair audio from generated videos. The story app can export a Timeline project package with assets and voice audio, ready for further video generation, timeline arrangement, editing and composition in Timeline. Individual images and audio files can also be imported separately.

A useful combination for creators making AI short films, animated stories or music videos locally. Visit the [ComfyUI-Capricorncd-Timeline project](https://github.com/capricorncd/ComfyUI-Capricorncd-Timeline) for installation and usage instructions, and prepare the GPU memory and runtime required by your chosen models.

## Development

`npm run dev` and `npm run build` default to the audio application.

Use `npm run image:tauri -- dev` for the image app, `npm run story:tauri -- dev` for the story app, or `npm run build:all` for all frontends. First install image dependencies with `apps/image/scripts/setup.ps1`. The image API uses port 19877; the audio API uses 19876; story uses 19878. Their histories, configurations and desktop identifiers are independent.
