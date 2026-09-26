$ErrorActionPreference = 'Stop'
$storyRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$workspaceRoot = (Resolve-Path (Join-Path $storyRoot '../..')).Path
$storyPython = Join-Path $workspaceRoot 'runtimes/image/Scripts/python.exe'
& $storyPython -m pip install -r (Join-Path $storyRoot 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Story dependencies could not be installed' }
