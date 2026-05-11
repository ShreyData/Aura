import asyncio
import json
import uuid
from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from aura.api.deps import get_ollama_client
from aura.api.schemas import ChatCompletionRequest, ChatMessage
from aura.config import get_config
from aura.events import EventBus, get_event_bus
from aura.io.prompt_composer import build_messages
from aura.ollama.client import OllamaClient, ToolCallDetected

router = APIRouter()
logger = structlog.get_logger()


class ConnectionManager:
    """
    Manages active WebSocket connections and their associated tasks.
    """

    def __init__(self) -> None:
        # Maps WebSocket to a dict of active request_id -> asyncio.Task
        self.active_connections: Dict[WebSocket, Dict[str, asyncio.Task]] = {}

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections[websocket] = {}
        logger.info("websocket_connected", total_connections=len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            # Cancel all running tasks for this connection
            for task in self.active_connections[websocket].values():
                if not task.done():
                    task.cancel()
            del self.active_connections[websocket]
            logger.info("websocket_disconnected", total_connections=len(self.active_connections))

    async def send_personal_message(self, message: Dict[str, Any], websocket: WebSocket) -> None:
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error("websocket_send_failed", error=str(e))

    async def broadcast(self, message: Dict[str, Any]) -> None:
        """
        Broadcasts a message to all connected clients.
        """
        for websocket in list(self.active_connections.keys()):
            try:
                await websocket.send_json(message)
            except Exception:
                # If sending fails, the connection might be dead; it will be cleaned up by the loop
                pass

    def register_task(self, websocket: WebSocket, request_id: str, task: asyncio.Task) -> None:
        if websocket in self.active_connections:
            self.active_connections[websocket][request_id] = task

    def cancel_task(self, websocket: WebSocket, request_id: str) -> bool:
        if websocket in self.active_connections and request_id in self.active_connections[websocket]:
            task = self.active_connections[websocket][request_id]
            if not task.done():
                task.cancel()
            del self.active_connections[websocket][request_id]
            return True
        return False


manager = ConnectionManager()


async def forward_events_to_ws() -> None:
    """
    Subscriber for the internal event bus that forwards events to all WS clients.
    Mappings follow docs/API_Contract.md.
    """
    bus = get_event_bus()

    async def on_event(event_type: str, payload: Any) -> None:
        # Map internal event types to WebSocket event types
        ws_type = event_type
        if event_type == "tool_approval_requested":
            ws_type = "tool_approval_needed"

        await manager.broadcast({"type": ws_type, "payload": payload})

    # Subscribe to all events
    await bus.subscribe("*", on_event)


@router.websocket("/v1/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    ollama: OllamaClient = Depends(get_ollama_client),
    event_bus: EventBus = Depends(get_event_bus),
) -> None:
    """
    Main WebSocket endpoint for real-time communication.
    """
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                msg_type = message.get("type")
                payload = message.get("payload", {})
            except json.JSONDecodeError:
                await manager.send_personal_message(
                    {"type": "error", "payload": {"code": "invalid_json", "message": "Invalid JSON"}},
                    websocket,
                )
                continue

            if msg_type == "ping":
                await manager.send_personal_message({"type": "pong", "payload": {}}, websocket)

            elif msg_type == "chat":
                request_id = payload.get("request_id") or str(uuid.uuid4())
                messages = payload.get("messages", [])
                stream = payload.get("stream", True)
                model = payload.get("model") or get_config().default_model

                # Start chat as a background task so we can receive other messages (like cancel)
                task = asyncio.create_task(
                    handle_ws_chat(websocket, request_id, model, messages, ollama, event_bus)
                )
                manager.register_task(websocket, request_id, task)

            elif msg_type == "cancel":
                request_id = payload.get("request_id")
                if request_id:
                    cancelled = manager.cancel_task(websocket, request_id)
                    logger.info("ws_chat_cancelled", request_id=request_id, success=cancelled)
                else:
                    logger.warning("ws_cancel_missing_request_id")

            else:
                logger.warning("ws_unknown_message_type", msg_type=msg_type)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error("websocket_handler_error", error=str(e))
        manager.disconnect(websocket)


async def handle_ws_chat(
    websocket: WebSocket,
    request_id: str,
    model: str,
    messages: List[Dict[str, Any]],
    ollama: OllamaClient,
    event_bus: EventBus,
) -> None:
    """
    Handles a chat request initiated over WebSocket.
    """
    try:
        # Signal thinking state
        await event_bus.publish("orb_state", {"state": "thinking"})

        # Build messages using the same logic as the REST API
        # Note: In a real implementation, we'd also pass screen captures/RAG context here
        final_messages = build_messages(messages=messages)

        try:
            async for token in ollama.stream_chat(model=model, messages=final_messages):
                await manager.send_personal_message(
                    {"type": "chat_chunk", "payload": {"delta": token, "request_id": request_id}},
                    websocket,
                )
        except ToolCallDetected as e:
            # For Phase 1, we log and signal but complex multi-turn WS tool calls 
            # might need a more robust state machine. 
            # Here we follow the simple path: notify the UI.
            await manager.send_personal_message(
                {
                    "type": "tool_call_start",
                    "payload": {"tool_name": e.tool_name, "args": e.args, "request_id": request_id},
                },
                websocket,
            )
            # Re-raise or handle approval flow if needed. 
            # For now, we terminate this WS chat task and expect the UI to handle tool flow via REST/Events.
            logger.info("ws_tool_call_detected", tool_name=e.tool_name)

        # Signal completion
        await manager.send_personal_message(
            {
                "type": "chat_done",
                "payload": {
                    "request_id": request_id,
                    "usage": {"prompt_tokens": 0, "completion_tokens": 0},
                },
            },
            websocket,
        )

    except asyncio.CancelledError:
        logger.info("ws_chat_task_cancelled", request_id=request_id)
    except Exception as e:
        logger.error("ws_chat_handler_error", request_id=request_id, error=str(e))
        await manager.send_personal_message(
            {"type": "error", "payload": {"code": "internal_error", "message": str(e)}},
            websocket,
        )
    finally:
        await event_bus.publish("orb_state", {"state": "idle"})
        # Clean up task from manager
        if websocket in manager.active_connections:
            manager.active_connections[websocket].pop(request_id, None)
