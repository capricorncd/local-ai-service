$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
& npm.cmd run build
if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
& cargo build --manifest-path src-tauri/Cargo.toml --release --features custom-protocol --locked
if ($LASTEXITCODE -ne 0) { throw 'Desktop build failed' }
Copy-Item -LiteralPath src-tauri/target/release/local-ai-service.exe -Destination Local-AI-Service.exe -Force
Write-Host 'Built Local-AI-Service.exe. Keep server/ and runtimes/ next to it.'
