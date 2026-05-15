#!/bin/bash
# scripts/build_core.sh
# Builds the aura-core sidecar executable using PyInstaller

DEST_DIR="ui/src-tauri/binaries"
mkdir -p "$DEST_DIR"

# Detect architecture for Tauri sidecar naming
OS_TYPE=$(uname -s)
ARCH_TYPE=$(uname -m)

if [ "$OS_TYPE" == "Linux" ]; then
    TRIPLE="x86_64-unknown-linux-gnu"
elif [ "$OS_TYPE" == "Darwin" ]; then
    if [ "$ARCH_TYPE" == "arm64" ]; then
        TRIPLE="aarch64-apple-darwin"
    else
        TRIPLE="x86_64-apple-darwin"
    fi
fi

echo "Building aura-core sidecar for $TRIPLE..."

cd core
uvx pyinstaller --onefile --name aura-core --clean \
    --hidden-import uvicorn.logging \
    --hidden-import uvicorn.loops \
    --hidden-import uvicorn.loops.auto \
    --hidden-import uvicorn.protocols \
    --hidden-import uvicorn.protocols.http \
    --hidden-import uvicorn.protocols.http.auto \
    --hidden-import uvicorn.protocols.websockets \
    --hidden-import uvicorn.protocols.websockets.auto \
    --hidden-import uvicorn.lifespan \
    --hidden-import uvicorn.lifespan.on \
    cli.py

if [ $? -eq 0 ]; then
    src="dist/aura-core"
    dest="../$DEST_DIR/aura-core-$TRIPLE"
    mv "$src" "$dest"
    chmod +x "$dest"
    echo "Successfully built $dest"
else
    echo "Failed to build aura-core sidecar."
    exit 1
fi

cd ..
