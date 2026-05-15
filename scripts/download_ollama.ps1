# scripts/download_ollama.ps1
# Downloads Ollama binaries for all supported platforms into ui/src-tauri/binaries/

$VERSION = "v0.1.33"
$BASE_URL = "https://github.com/ollama/ollama/releases/download/$VERSION"
$DEST_DIR = "ui/src-tauri/binaries"

if (-not (Test-Path $DEST_DIR)) {
    New-Item -ItemType Directory -Path $DEST_DIR
}

$BINARIES = @(
    @{
        Remote = "ollama-windows-amd64.exe"
        Local  = "ollama-x86_64-pc-windows-msvc.exe"
    },
    @{
        Remote = "ollama-darwin-amd64"
        Local  = "ollama-x86_64-apple-darwin"
    },
    @{
        Remote = "ollama-darwin-arm64"
        Local  = "ollama-aarch64-apple-darwin"
    },
    @{
        Remote = "ollama-linux-amd64"
        Local  = "ollama-x86_64-unknown-linux-gnu"
    }
)

foreach ($bin in $BINARIES) {
    $url = "$BASE_URL/$($bin.Remote)"
    $dest = "$DEST_DIR/$($bin.Local)"
    
    Write-Host "Downloading $($bin.Remote) to $dest..."
    Invoke-WebRequest -Uri $url -OutFile $dest
}

Write-Host "Ollama binaries download complete."
