# scripts/build_core.ps1
# Builds the aura-core sidecar executable using PyInstaller

$DEST_DIR = "ui/src-tauri/binaries"
if (-not (Test-Path $DEST_DIR)) {
    New-Item -ItemType Directory -Path $DEST_DIR
}

# Detect architecture for Tauri sidecar naming
$ARCH = "x86_64-pc-windows-msvc" # Default for Windows x64

Write-Host "Building aura-core sidecar for $ARCH..."

# Use uvx to run pyinstaller without adding it to project dependencies
# We package cli.py as the entry point
cd core
uvx pyinstaller --onefile --name aura-core --clean `
    --hidden-import uvicorn.logging `
    --hidden-import uvicorn.loops `
    --hidden-import uvicorn.loops.auto `
    --hidden-import uvicorn.protocols `
    --hidden-import uvicorn.protocols.http `
    --hidden-import uvicorn.protocols.http.auto `
    --hidden-import uvicorn.protocols.websockets `
    --hidden-import uvicorn.protocols.websockets.auto `
    --hidden-import uvicorn.lifespan `
    --hidden-import uvicorn.lifespan.on `
    cli.py

if ($LASTEXITCODE -eq 0) {
    $src = "dist/aura-core.exe"
    $dest = "../$DEST_DIR/aura-core-$ARCH.exe"
    Move-Item -Path $src -Destination $dest -Force
    Write-Host "Successfully built $dest"
} else {
    Write-Error "Failed to build aura-core sidecar."
}

cd ..
