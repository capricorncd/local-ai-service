param([switch]$DownloadModel)
$ErrorActionPreference = 'Stop'
$appRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $appRoot
$env:UV_CACHE_DIR = Join-Path $appRoot 'runtimes/uv-cache'
$env:HF_HOME = Join-Path $appRoot 'runtimes/hf-cache'
$uvPath = Join-Path $appRoot 'runtimes/tools/uv.exe'
function Run-UV { & $uvPath @args; if ($LASTEXITCODE -ne 0) { throw "uv failed: $args" } }
$revision = '934d6826b084c46a0d033402174d5f8ac4ed2519'
if (-not (Test-Path -LiteralPath 'runtimes/MOSS-TTS/moss_soundeffect_v2/pyproject.toml')) {
    Invoke-WebRequest "https://github.com/OpenMOSS/MOSS-TTS/archive/$revision.zip" -OutFile runtimes/moss-runtime.zip
    Expand-Archive -LiteralPath runtimes/moss-runtime.zip -DestinationPath runtimes -Force
    $sourceDir = [IO.Path]::GetFullPath((Join-Path $appRoot "runtimes/MOSS-TTS-$revision"))
    $targetDir = [IO.Path]::GetFullPath((Join-Path $appRoot 'runtimes/MOSS-TTS'))
    if (-not $sourceDir.StartsWith($appRoot + '\') -or -not $targetDir.StartsWith($appRoot + '\')) { throw 'Runtime outside app' }
    if (Test-Path -LiteralPath $targetDir) { throw 'Inspect existing incomplete MOSS-TTS directory before retrying.' }
    Move-Item -LiteralPath $sourceDir -Destination $targetDir
}
if (-not (Test-Path -LiteralPath 'runtimes/sfx/Scripts/python.exe')) {
    Run-UV venv --python runtimes/python/cpython-3.12.13-windows-x86_64-none/python.exe runtimes/sfx
}
Run-UV pip sync --python runtimes/sfx/Scripts/python.exe requirements/sfx.lock.txt --extra-index-url https://download.pytorch.org/whl/cu128 --index-strategy unsafe-best-match
Run-UV pip install --python runtimes/sfx/Scripts/python.exe --no-deps ./runtimes/MOSS-TTS/moss_soundeffect_v2
if ($DownloadModel) {
    & runtimes/sfx/Scripts/python.exe -c "from huggingface_hub import snapshot_download; snapshot_download('OpenMOSS-Team/MOSS-SoundEffect-v2.0',local_dir='runtimes/models/MOSS-SoundEffect-v2.0')"
    if ($LASTEXITCODE -ne 0) { throw 'Sound effect model download failed' }
}
Write-Host 'Sound effect runtime ready. Configure and restart the sfx service.'
