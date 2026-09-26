$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$uv = Join-Path $projectRoot 'runtimes/tools/uv.exe'
$python = Join-Path $projectRoot 'runtimes/api/Scripts/python.exe'
$envPath = Join-Path $projectRoot 'runtimes/image'
$imagePython = Join-Path $envPath 'Scripts/python.exe'
$core = Join-Path $projectRoot 'runtimes/image-core'
$revision = 'b33e2b55cae074eca5aec96283cceac19aa249ba'
function Assert-Success { if ($LASTEXITCODE -ne 0) { throw "Setup failed with exit code $LASTEXITCODE" } }
if (!(Test-Path -LiteralPath $core)) {
    git clone https://github.com/Comfy-Org/ComfyUI.git $core
    Assert-Success
}
git -C $core checkout $revision
Assert-Success
if (!(Test-Path -LiteralPath $imagePython)) {
    & $uv venv --python $python $envPath
    Assert-Success
}
& $uv pip install --python $imagePython 'torch==2.10.0' 'torchvision==0.25.0' --index-url https://download.pytorch.org/whl/cu128
Assert-Success
& $uv pip install --python $imagePython -r (Join-Path $PSScriptRoot '../requirements.txt')
Assert-Success
Write-Host 'Image runtime is ready. Model weights are loaded directly from the configured directory.'
