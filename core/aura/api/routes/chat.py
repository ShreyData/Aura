import asyncio
import json
import time
import uuid
from typing import Annotated, Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from aura.api.deps import get_ollama_client
from aura.api.schemas import (
    ChatCompletionChunk,
    ChatCompletionChunkChoice,
    ChatCompletionChunkDelta,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionResponseChoice,
    ChatMessage,
    PendingToolCall,
)
from aura.config import Settings, get_config
from aura.events import EventBus, get_event_bus
from aura.io.prompt_composer import build_messages
from aura.ollama.client import OllamaClient, ToolCallDetected

router = APIRouter()
logger = structlog.get_logger()


async def wait_for_tool_approval(request_id: str, event_bus: EventBus) -> bool:
    """
    Wait for a tool approval event on the event bus.
    """
    loop = asyncio.get_running_loop()
    future = loop.create_future()

    async def on_approval(event_type: str, payload: Dict[str, Any]) -> None:
        if payload.get("request_id") == request_id:
            future.set_result(payload.get("approved", False))

    await event_bus.subscribe("tool_approved", on_approval)
    try:
        # Wait for up to 60 seconds for user approval
        approved = await asyncio.wait_for(future, timeout=60.0)
        return approved
    except asyncio.TimeoutError:
        logger.warning("tool_approval_timeout", request_id=request_id)
        return False
    finally:
        await event_bus.unsubscribe("tool_approved", on_approval)


async def execute_tool(tool_name: str, args: Dict[str, Any]) -> Any:
    """
    Placeholder for tool execution logic.
    In a full implementation, this would route to the appropriate tool handler.
    """
    logger.info("executing_tool", tool_name=tool_name, args=args)
    # TODO: Implement actual tool execution registry in Step 2.x
    return {"status": "success", "message": f"Tool {tool_name} executed (placeholder)"}


@router.post("/v1/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    ollama: Annotated[OllamaClient, Depends(get_ollama_client)],
    event_bus: Annotated[EventBus, Depends(get_event_bus)],
    config: Annotated[Settings, Depends(get_config)],
) -> Any:
    """
    OpenAI-compatible chat completion endpoint.
    Supports streaming, tool calls with approval gates, and orb state events.
    """
    request_id = f"chatcmpl-{uuid.uuid4()}"
    created_time = int(time.time())

    # Build initial message list including system prompt and context
    # We convert Pydantic models to dicts for the prompt composer
    raw_messages = [m.model_dump(exclude_none=True) for m in request.messages]
    messages = build_messages(
        messages=raw_messages,
        tool_schemas=request.tools,
    )

    async def stream_generator():
        nonlocal messages
        # Signal that Aura is thinking
        await event_bus.publish("orb_state", {"state": "thinking"})

        try:
            while True:
                try:
                    # Start or resume inference with current message history
                    async for token in ollama.stream_chat(
                        model=request.model,
                        messages=messages,
                        tools=request.tools,
                    ):
                        chunk = ChatCompletionChunk(
                            id=request_id,
                            created=created_time,
                            model=request.model,
                            choices=[
                                ChatCompletionChunkChoice(
                                    index=0,
                                    delta=ChatCompletionChunkDelta(content=token),
                                    finish_reason=None,
                                )
                            ],
                        )
                        yield f"data: {chunk.model_dump_json()}\n\n"

                    # Successfully finished stream without further tool calls
                    final_chunk = ChatCompletionChunk(
                        id=request_id,
                        created=created_time,
                        model=request.model,
                        choices=[
                            ChatCompletionChunkChoice(
                                index=0,
                                delta=ChatCompletionChunkDelta(),
                                finish_reason="stop",
                            )
                        ],
                    )
                    yield f"data: {final_chunk.model_dump_json()}\n\n"
                    yield "data: [DONE]\n\n"
                    break

                except ToolCallDetected as e:
                    logger.info("tool_call_detected", tool_name=e.tool_name)
                    
                    # Generate a unique ID for this tool call instance
                    tool_call_id = str(uuid.uuid4())
                    
                    # 1. Approval Gate
                    approved = True
                    # Only require approval if configured
                    if config.require_approval_medium:
                        # Publish pending tool call event for the UI/WebSocket
                        pending = PendingToolCall(
                            request_id=tool_call_id,
                            tool_name=e.tool_name,
                            args=e.args,
                            risk_level="medium",
                        )
                        await event_bus.publish("tool_approval_requested", pending.model_dump())
                        
                        # Pause and wait for UI approval via event bus
                        approved = await wait_for_tool_approval(tool_call_id, event_bus)

                    if approved:
                        # 2. Execute Tool
                        result = await execute_tool(e.tool_name, e.args)
                        
                        # 3. Inject result and resume
                        # Add assistant's partial response + the tool call to history
                        messages.append({
                            "role": "assistant",
                            "content": e.partial_response,
                            "tool_calls": [
                                {
                                    "id": tool_call_id,
                                    "type": "function",
                                    "function": {
                                        "name": e.tool_name,
                                        "arguments": json.dumps(e.args)
                                    }
                                }
                            ]
                        })
                        # Add the tool's output to history
                        messages.append({
                            "role": "tool",
                            "name": e.tool_name,
                            "content": json.dumps(result)
                        })
                        
                        logger.info("resuming_after_tool_call", tool_name=e.tool_name)
                        # Loop continues, calling ollama.stream_chat again with updated history
                    else:
                        # Tool denied: notify the user in the stream and stop
                        denial_msg = "\n[Tool call denied by user]"
                        chunk = ChatCompletionChunk(
                            id=request_id,
                            created=created_time,
                            model=request.model,
                            choices=[
                                ChatCompletionChunkChoice(
                                    index=0,
                                    delta=ChatCompletionChunkDelta(content=denial_msg),
                                    finish_reason="stop",
                                )
                            ],
                        )
                        yield f"data: {chunk.model_dump_json()}\n\n"
                        yield "data: [DONE]\n\n"
                        break

        except Exception as err:
            logger.error("stream_generation_error", error=str(err))
            yield f"data: {json.dumps({'error': str(err)})}\n\n"
        finally:
            # Signal that Aura is back to idle
            await event_bus.publish("orb_state", {"state": "idle"})

    if request.stream:
        return StreamingResponse(stream_generator(), media_type="text/event-stream")

    # Non-streaming implementation: collect chunks and return a single response
    full_content = ""
    async for chunk_str in stream_generator():
        if chunk_str.startswith("data: ") and not chunk_str.endswith("[DONE]\n\n"):
            try:
                data = json.loads(chunk_str[6:])
                choices = data.get("choices", [])
                if choices and choices[0]["delta"].get("content"):
                    full_content += choices[0]["delta"]["content"]
            except (json.JSONDecodeError, KeyError, IndexError):
                continue

    return ChatCompletionResponse(
        id=request_id,
        created=created_time,
        model=request.model,
        choices=[
            ChatCompletionResponseChoice(
                index=0,
                message=ChatMessage(role="assistant", content=full_content),
                finish_reason="stop",
            )
        ],
        usage=None,
    )
