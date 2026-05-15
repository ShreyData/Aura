#!/bin/bash
# scripts/download_ollama.sh
# Downloads Ollama binaries for all supported platforms into ui/src-tauri/binaries/

VERSION="v0.1.33"
BASE_URL="https://github.com/ollama/ollama/releases/download/$VERSION"
DEST_DIR="ui/src-tauri/binaries"

mkdir -p "$DEST_DIR"

declare -A BINARIES=(
    ["ollama-windows-amd64.exe"]="ollama-x86_64-pc-windows-msvc.exe"
    ["ollama-darwin-amd64"]="ollama-x86_64-apple-darwin"
    ["ollama-darwin-arm64"]="ollama-aarch64-apple-darwin"
    ["ollama-linux-amd64"]="ollama-x86_64-unknown-linux-gnu"
)

for remote in "${!BINARIES[@]}"; do
    local="${BINARIES[$remote]}"
    url="$BASE_URL/$remote"
    dest="$DEST_DIR/$local"
    
    echo "Downloading $remote to $dest..."
    curl -L "$url" -o "$dest"
    chmod +x "$dest"
done

echo "Ollama binaries download complete."
