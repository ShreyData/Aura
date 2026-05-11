import time
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from aura.api.deps import get_ollama_client, get_ollama_manager
from aura.api.schemas import HealthResponse
from aura.ollama.client import OllamaClient
from aura.ollama.manager import OllamaManager

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def get_health(
    request: Request,
    ollama_client: Annotated[OllamaClient, Depends(get_ollama_client)],
    ollama_manager: Annotated[OllamaManager, Depends(get_ollama_manager)],
) -> HealthResponse:
    """
    Returns system health status for both Aura Core and internal Ollama.
    Returns HTTP 200 even if Ollama is offline.
    """
    # Aura is online if this code is running
    aura_online = True
    
    # Check Ollama health
    ollama_online = await ollama_client.health()
    
    # Get currently active model from manager
    active_model = None
    if ollama_online:
        status = await ollama_manager.get_model_status()
        active_model = status.get("model")

    # Calculate uptime (startup time will be set in main.py)
    # Default to 0 if not found in state
    start_time = getattr(request.app.state, "start_time", time.time())
    uptime_s = int(time.time() - start_time)

    return HealthResponse(
        aura=aura_online,
        ollama=ollama_online,
        active_model=active_model,
        uptime_s=uptime_s,
    )
