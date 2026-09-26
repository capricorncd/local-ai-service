param([switch]$DownloadModels, [switch]$PrepareVoices)
$ErrorActionPreference = 'Stop'
$appRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $appRoot
$env:UV_CACHE_DIR = Join-Path $appRoot 'runtimes/uv-cache'
$env:HF_HOME = Join-Path $appRoot 'runtimes/hf-cache'
$uvPath = Join-Path $appRoot 'runtimes/tools/uv.exe'
function Run-UV { & $uvPath @args; if ($LASTEXITCODE -ne 0) { throw "uv failed: $args" } }
$revision = '51383efd921027683c89e5348211d93ff12ac2a8'
if (-not (Test-Path -LiteralPath 'runtimes/Seed-VC/inference.py')) {
    Invoke-WebRequest "https://github.com/Plachtaa/seed-vc/archive/$revision.zip" -OutFile runtimes/seed-runtime.zip
    Expand-Archive -LiteralPath runtimes/seed-runtime.zip -DestinationPath runtimes -Force
    $sourceDir = [IO.Path]::GetFullPath((Join-Path $appRoot "runtimes/seed-vc-$revision"))
    $targetDir = [IO.Path]::GetFullPath((Join-Path $appRoot 'runtimes/Seed-VC'))
    if (-not $sourceDir.StartsWith($appRoot + '\') -or -not $targetDir.StartsWith($appRoot + '\')) { throw 'Runtime outside app' }
    if (Test-Path -LiteralPath $targetDir) { throw 'Inspect existing incomplete Seed-VC directory before retrying.' }
    Move-Item -LiteralPath $sourceDir -Destination $targetDir
}
foreach ($service in @('tts','vc')) {
    if (-not (Test-Path -LiteralPath "runtimes/$service/Scripts/python.exe")) {
        Run-UV venv --python runtimes/python/cpython-3.12.13-windows-x86_64-none/python.exe "runtimes/$service"
    }
    Run-UV pip sync --python "runtimes/$service/Scripts/python.exe" "requirements/$service.lock.txt" --extra-index-url https://download.pytorch.org/whl/cu128 --index-strategy unsafe-best-match
}
if ($DownloadModels) {
    & runtimes/tts/Scripts/python.exe scripts/download-voice-models.py
    if ($LASTEXITCODE -ne 0) { throw 'Voice model download failed' }
}
if ($PrepareVoices) {
    & runtimes/tts/Scripts/python.exe scripts/prepare-voices.py
    if ($LASTEXITCODE -ne 0) { throw 'Preset reference preparation failed' }
}
Write-Host 'Voice environments ready. Configure and restart tts/vc services.'
