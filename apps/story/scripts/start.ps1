$ErrorActionPreference = 'Stop'
$storyRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$workspaceRoot = (Resolve-Path (Join-Path $storyRoot '../..')).Path
$storyPython = Join-Path $workspaceRoot 'runtimes/image/Scripts/python.exe'
& $storyPython (Join-Path $storyRoot 'server/run.py') --data-dir (Join-Path $workspaceRoot 'data/story') --port 19878
