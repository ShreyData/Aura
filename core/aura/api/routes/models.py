import asyncio
import json
from typing import Annotated, Any, Dict, List

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from aura.api.deps import get_ollama_client, get_ollama_manager, get_event_bus
from aura.config import get_config
from aura.events import EventBus
from aura.ollama.client import OllamaClient
from aura.ollama.manager import OllamaManager

router = APIRouter()
logger = structlog.get_logger()

class ModelPullRequest(BaseModel):
    model: str

@router.get("/v1/models")
async def list_models(
    ollama_client: Annotated[OllamaClient, Depends(get_ollama_client)],
    ollama_manager: Annotated[OllamaManager, Depends(get_ollama_manager)],
) -> Dict[str, Any]:
    """
    Returns a list of all downloaded models and the currently active model.
    """
    models = await ollama_client.list_models()
    status = await ollama_manager.get_model_status()
    
    return {
        "models": models,
        "active_model": status.get("model"),
        "active_model_vram": status.get("size_vram", 0),
        "status": status
    }

@router.get("/v1/models/recommend")
async def recommend_model(
    ollama_manager: Annotated[OllamaManager, Depends(get_ollama_manager)],
) -> Dict[str, str]:
    """
    Returns a hardware-aware model recommendation based on system RAM.
    """
    recommended = ollama_manager.get_recommended_model()
    return {"recommended_model": recommended}

@router.post("/v1/models/pull")
async def pull_model(
    request: ModelPullRequest,
    ollama_client: Annotated[OllamaClient, Depends(get_ollama_client)],
    event_bus: Annotated[EventBus, Depends(get_event_bus)],
) -> StreamingResponse:
    """
    Downloads a model from the Ollama library.
    Streams progress as SSE events and publishes to the event bus for WebSocket clients.
    """
    async def progress_generator():
        queue = asyncio.Queue()

        async def on_progress(data: Dict[str, Any]) -> None:
            # Wrap callback data into a thread-safe-ish queue for the generator
            queue.put_nowait(data)
            
            # Also publish to the event bus for WebSocket clients
            event_payload = {
                "model": request.model,
                "status": data.get("status"),
                "percent": data.get("percent"),
                "completed": data.get("completed"),
                "total": data.get("total"),
            }
            await event_bus.publish("model_pull_progress", event_payload)

        # Start the pull operation
        pull_task = asyncio.create_task(ollama_client.pull_model(request.model, on_progress))

        try:
            while not pull_task.done() or not queue.empty():
                try:
                    # Wait for progress data
                    progress = await asyncio.wait_for(queue.get(), timeout=0.1)
                    
                    # Format as the WebSocket event shape defined in API_Contract.md
                    event = {
                        "type": "model_pull_progress",
                        "payload": {
                            "model": request.model,
                            "status": progress.get("status"),
                            "percent": progress.get("percent"),
                            "completed": progress.get("completed"),
                            "total": progress.get("total"),
                        }
                    }
                    yield f"data: {json.dumps(event)}\n\n"
                    queue.task_done()
                except asyncio.TimeoutError:
                    if pull_task.done():
                        break
                    continue
            
            # Ensure we catch any exceptions from the task
            await pull_task
            
        except Exception as e:
            logger.error("model_pull_stream_error", model=request.model, error=str(e))
            yield f"data: {json.dumps({'type': 'error', 'payload': {'message': str(e)}})}\n\n"

    return StreamingResponse(progress_generator(), media_type="text/event-stream")

@router.delete("/v1/models/{name}")
async def delete_model(
    name: str,
    ollama_client: Annotated[OllamaClient, Depends(get_ollama_client)],
) -> Dict[str, str]:
    """
    Deletes a model from local storage.
    """
    try:
        await ollama_client.delete_model(name)
        return {"status": "success", "message": f"Model {name} deleted"}
    except Exception as e:
        logger.error("model_delete_failed", model=name, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
