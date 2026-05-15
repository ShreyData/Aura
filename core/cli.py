import json
import sys
from typing import Optional

import httpx
import psutil
import typer
import uvicorn

from aura.config import get_config

app = typer.Typer(help="Aura CLI - Privacy-first AI assistant powered by Gemma 4")
models_app = typer.Typer(help="Manage local AI models")
app.add_typer(models_app, name="models")

CONFIG = get_config()
BASE_URL = f"http://127.0.0.1:{CONFIG.core_port}"


def get_client():
    """Returns an httpx client configured for the Aura Core API."""
    return httpx.Client(base_url=BASE_URL, timeout=None)


def check_core_running():
    """Checks if the Aura Core API is reachable."""
    try:
        with httpx.Client(base_url=BASE_URL, timeout=2.0) as client:
            response = client.get("/health")
            return response.status_code == 200
    except Exception:
        return False


@app.command()
def health():
    """Print a formatted health response of the system."""
    try:
        with get_client() as client:
            response = client.get("/health")
            response.raise_for_status()
            data = response.json()

            typer.secho("\n--- Aura Health Status ---", bold=True)

            aura_status = "ONLINE" if data["aura"] else "OFFLINE"
            aura_color = typer.colors.GREEN if data["aura"] else typer.colors.RED
            typer.echo("Aura Core: ", nl=False)
            typer.secho(aura_status, fg=aura_color, bold=True)

            ollama_status = "ONLINE" if data["ollama"] else "OFFLINE"
            ollama_color = typer.colors.GREEN if data["ollama"] else typer.colors.RED
            typer.echo("Ollama:    ", nl=False)
            typer.secho(ollama_status, fg=ollama_color, bold=True)

            typer.echo(f"Active Model: {data.get('active_model') or 'None'}")
            typer.echo(f"Uptime:       {data['uptime_s']}s\n")

    except httpx.ConnectError:
        typer.secho(
            "\nError: Aura Core is not running. Start it with 'aura serve'.",
            fg=typer.colors.RED,
            err=True,
        )
        sys.exit(1)


@app.command()
def system():
    """Print hardware info and the recommended model for this machine."""
    ram = psutil.virtual_memory()
    total_ram_gb = ram.total / (1024**3)
    available_ram_gb = ram.available / (1024**3)

    typer.secho("\n--- System Hardware ---", bold=True)
    typer.echo(f"Total RAM:     {total_ram_gb:.2f} GB")
    typer.echo(f"Available RAM: {available_ram_gb:.2f} GB")

    # Recommendation logic (proxied via core if running, otherwise local fallback)
    recommended = None
    try:
        if check_core_running():
            with get_client() as client:
                response = client.get("/v1/models/recommend")
                recommended = response.json().get("recommended_model")
    except Exception:
        pass

    if not recommended:
        # Fallback to local logic if core is offline
        if total_ram_gb < 16:
            recommended = "gemma4:e2b"
        elif total_ram_gb < 32:
            recommended = "gemma4:e4b"
        elif total_ram_gb < 64:
            recommended = "gemma4:26b"
        else:
            recommended = "gemma4:31b"

    typer.echo("Recommended:   ", nl=False)
    typer.secho(recommended, fg=typer.colors.GREEN, bold=True)
    typer.echo()


@app.command()
def chat(
    message: str,
    model: Optional[str] = typer.Option(None, "--model", help="Specify model to use"),
    no_stream: bool = typer.Option(
        False, "--no-stream", help="Disable streaming output"
    ),
):
    """Send a message to Aura and receive a response."""
    selected_model = model or CONFIG.default_model
    payload = {
        "model": selected_model,
        "messages": [{"role": "user", "content": message}],
        "stream": not no_stream,
    }

    try:
        with httpx.Client(base_url=BASE_URL, timeout=None) as client:
            if no_stream:
                response = client.post("/v1/chat/completions", json=payload)
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                typer.echo(content)
            else:
                with client.stream(
                    "POST", "/v1/chat/completions", json=payload
                ) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if not line:
                            continue
                        if line.startswith("data: "):
                            if line == "data: [DONE]":
                                break
                            try:
                                chunk = json.loads(line[6:])
                                content = chunk["choices"][0]["delta"].get(
                                    "content", ""
                                )
                                if content:
                                    print(content, end="", flush=True)
                            except Exception:
                                continue
                print()  # Final newline
    except httpx.ConnectError:
        typer.secho(
            "Error: Aura Core is not running. Start it with 'aura serve'.",
            fg=typer.colors.RED,
            err=True,
        )
        sys.exit(1)


@models_app.command("list")
def models_list():
    """List all locally downloaded models."""
    try:
        with get_client() as client:
            response = client.get("/v1/models")
            response.raise_for_status()
            data = response.json()

            models = data.get("models", [])
            active = data.get("active_model")

            if not models:
                typer.echo(
                    "No models downloaded yet. Use 'aura models pull <name>' to get one."
                )
                return

            typer.echo(f"\n{'NAME':<30} {'SIZE':<10} {'ID':<15}")
            typer.echo("-" * 55)
            for m in models:
                name = m["name"]
                size_gb = m.get("size", 0) / (1024**3)
                digest = m.get("digest", "unknown")[:12]

                prefix = "* " if name == active or f"{name}:latest" == active else "  "
                line = f"{prefix}{name:<28} {size_gb:>6.2f} GB    {digest}"

                if prefix == "* ":
                    typer.secho(line, fg=typer.colors.CYAN, bold=True)
                else:
                    typer.echo(line)
            typer.echo()

    except httpx.ConnectError:
        typer.secho("Error: Aura Core is not running.", fg=typer.colors.RED, err=True)
        sys.exit(1)


@models_app.command("pull")
def models_pull(name: str):
    """Download a new model from the library."""
    try:
        with httpx.Client(base_url=BASE_URL, timeout=None) as client:
            with client.stream(
                "POST", "/v1/models/pull", json={"model": name}
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        if data["type"] == "model_pull_progress":
                            payload = data["payload"]
                            status = payload.get("status", "Pulling")
                            percent = payload.get("percent", 0)
                            print(f"\r{status}: {percent}%", end="", flush=True)
                print(f"\nSuccessfully pulled model: {name}")
    except httpx.ConnectError:
        typer.secho("Error: Aura Core is not running.", fg=typer.colors.RED, err=True)
        sys.exit(1)


@models_app.command("delete")
def models_delete(name: str):
    """Delete a locally stored model."""
    try:
        with get_client() as client:
            response = client.delete(f"/v1/models/{name}")
            response.raise_for_status()
            typer.secho(f"Successfully deleted model: {name}", fg=typer.colors.GREEN)
    except httpx.ConnectError:
        typer.secho("Error: Aura Core is not running.", fg=typer.colors.RED, err=True)
        sys.exit(1)


@app.command()
def serve(
    port: Optional[int] = typer.Option(None, "--port", help="Override default port"),
):
    """Start the Aura Core FastAPI server."""
    port = port or CONFIG.core_port
    typer.secho(
        f"Starting Aura Core on 127.0.0.1:{port}...", fg=typer.colors.CYAN, bold=True
    )
    # Mandate check: Bind only to 127.0.0.1
    uvicorn.run("aura.main:app", host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    app()
