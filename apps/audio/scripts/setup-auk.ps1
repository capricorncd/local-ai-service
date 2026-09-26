$ErrorActionPreference = 'Stop'
$appRoot = Split-Path -Parent $PSScriptRoot
$uv = Join-Path $appRoot 'runtimes/tools/uv.exe'
$env:UV_CACHE_DIR = Join-Path $appRoot 'runtimes/uv-cache'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $appRoot 'runtimes/python'
$env:HF_HOME = Join-Path $appRoot 'runtimes/hf-cache'
$env:UV_PYTHON_PREFERENCE = 'only-managed'
$env:UV_PYTHON = ''
if (-not (Test-Path -LiteralPath $uv)) { throw 'Missing app-local uv.exe' }
$source = Join-Path $appRoot 'runtimes/AuK'
if (-not (Test-Path -LiteralPath (Join-Path $source 'pyproject.toml'))) { throw 'Missing runtimes/AuK official source' }
$venv = Join-Path $appRoot 'runtimes/auk-env'
& $uv python install 3.10
if ($LASTEXITCODE -ne 0) { throw 'Python install failed' }
if (-not (Test-Path -LiteralPath (Join-Path $venv 'Scripts/python.exe'))) {
    & $uv venv --python 3.10 $venv
    if ($LASTEXITCODE -ne 0) { throw 'Environment creation failed' }
}
$python = Join-Path $venv 'Scripts/python.exe'
& $uv pip install --python $python --index-url https://download.pytorch.org/whl/cu128 torch==2.7.1 torchaudio==2.7.1 torchvision==0.22.1
if ($LASTEXITCODE -ne 0) { throw 'PyTorch install failed' }
& $uv pip install --python $python -e $source soundfile librosa transformers==4.57.6
if ($LASTEXITCODE -ne 0) { throw 'AuK dependencies install failed' }
& $python -c 'from auk.infer.infer_auk import AukInfer; print("AuK runtime ready; model weights are configured separately.")'
if ($LASTEXITCODE -ne 0) { throw 'AuK import check failed' }
