param([string]$FFmpegSource = '', [switch]$DownloadDenoiseModel, [switch]$DownloadSeparationModel)
$ErrorActionPreference = 'Stop'
$appRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $appRoot
$env:UV_PYTHON_INSTALL_DIR = Join-Path $appRoot 'runtimes/python'
$env:UV_CACHE_DIR = Join-Path $appRoot 'runtimes/uv-cache'
$env:HF_HOME = Join-Path $appRoot 'runtimes/hf-cache'
New-Item -ItemType Directory -Force runtimes/tools | Out-Null
$uvPath = Join-Path $appRoot 'runtimes/tools/uv.exe'
if (-not (Test-Path -LiteralPath $uvPath)) {
    $existingUv = Get-Command uv -ErrorAction SilentlyContinue
    if ($existingUv) { Copy-Item -LiteralPath $existingUv.Source -Destination $uvPath }
    else {
        Invoke-WebRequest 'https://github.com/astral-sh/uv/releases/download/0.11.17/uv-x86_64-pc-windows-msvc.zip' -OutFile runtimes/tools/uv.zip
        Expand-Archive -LiteralPath runtimes/tools/uv.zip -DestinationPath runtimes/tools -Force
    }
}
function Run-UV { & $uvPath @args; if ($LASTEXITCODE -ne 0) { throw "uv failed: $args" } }
Run-UV python install 3.12.13 --no-bin --no-registry
foreach ($service in @('api','music','denoise')) {
    if (-not (Test-Path -LiteralPath "runtimes/$service/Scripts/python.exe")) {
        Run-UV venv --managed-python --python 3.12.13 "runtimes/$service"
    }
    Run-UV pip sync --python "runtimes/$service/Scripts/python.exe" "requirements/$service.lock.txt" --extra-index-url https://download.pytorch.org/whl/cu128 --index-strategy unsafe-best-match
}
if (-not (Test-Path -LiteralPath 'runtimes/ComfyUI/comfy_extras/nodes_yue2.py')) {
    Invoke-WebRequest 'https://github.com/Comfy-Org/ComfyUI/archive/7a0b5eede3f9721c8faab290689893f36edc6d66.zip' -OutFile runtimes/comfy-runtime.zip
    Expand-Archive -LiteralPath runtimes/comfy-runtime.zip -DestinationPath runtimes -Force
    $sourceRuntime = [IO.Path]::GetFullPath((Join-Path $appRoot 'runtimes/ComfyUI-7a0b5eede3f9721c8faab290689893f36edc6d66'))
    $targetRuntime = [IO.Path]::GetFullPath((Join-Path $appRoot 'runtimes/ComfyUI'))
    if (-not $sourceRuntime.StartsWith($appRoot + '\') -or -not $targetRuntime.StartsWith($appRoot + '\')) { throw 'Runtime path outside app' }
    if (Test-Path -LiteralPath $targetRuntime) { throw 'Existing incomplete ComfyUI directory; inspect it before retrying.' }
    Move-Item -LiteralPath $sourceRuntime -Destination $targetRuntime
}
if (-not (Test-Path -LiteralPath 'runtimes/ffmpeg/bin/ffmpeg.exe')) {
    New-Item -ItemType Directory -Force runtimes/ffmpeg/bin | Out-Null
    if ($FFmpegSource) { Copy-Item -LiteralPath $FFmpegSource -Destination runtimes/ffmpeg/bin/ffmpeg.exe }
    else { Write-Warning 'Put a static FFmpeg executable at runtimes/ffmpeg/bin/ffmpeg.exe, or pass -FFmpegSource.' }
}
if ($DownloadDenoiseModel) {
    & runtimes/denoise/Scripts/python.exe -c "from huggingface_hub import snapshot_download; snapshot_download('alibabasglab/MossFormer2_SE_48K',local_dir='runtimes/models/MossFormer2_SE_48K',allow_patterns=['*.pt','last_best_checkpoint','README.md'])"
    if ($LASTEXITCODE -ne 0) { throw 'Model download failed' }
}
if ($DownloadSeparationModel) {
    & runtimes/denoise/Scripts/python.exe -c "from huggingface_hub import snapshot_download; snapshot_download('alibabasglab/MossFormer2_SS_16K',local_dir='runtimes/models/MossFormer2_SS_16K',allow_patterns=['*.pt','last_best_checkpoint','README.md'])"
    if ($LASTEXITCODE -ne 0) { throw 'Separation model download failed' }
}
Write-Host 'Isolated runtimes are ready. No system Python or other app packages were modified.'
