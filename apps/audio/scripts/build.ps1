$ErrorActionPreference = 'Stop'
$entryRoot = Split-Path -Parent $PSScriptRoot
# The root scripts/ and src-tauri/ are junctions. Use the physical app path so
# Tauri's ../dist resolves to apps/audio/dist, never the legacy root dist/.
$audioRoot = if (Test-Path -LiteralPath (Join-Path $entryRoot 'apps/audio/package.json')) {
    Join-Path $entryRoot 'apps/audio'
} else {
    $entryRoot
}
$repoRoot = Split-Path -Parent (Split-Path -Parent $audioRoot)
Set-Location -LiteralPath $audioRoot
& npm.cmd run build
if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
$manifest = Join-Path $audioRoot 'src-tauri/Cargo.toml'
& cargo build --manifest-path $manifest --release --features custom-protocol --locked
if ($LASTEXITCODE -ne 0) { throw 'Desktop build failed' }
$release = Join-Path $audioRoot 'src-tauri/target/release/local-ai-service.exe'
$destination = Join-Path $repoRoot 'Local-AI-Service.exe'
Copy-Item -LiteralPath $release -Destination $destination -Force
if ((Get-FileHash -LiteralPath $release).Hash -ne (Get-FileHash -LiteralPath $destination).Hash) {
    throw 'Desktop executable verification failed'
}
Write-Host "Built $destination using $audioRoot/dist."
