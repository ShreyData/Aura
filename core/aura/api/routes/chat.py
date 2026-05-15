import asyncio
import json
import time
import uuid
from typing import Annotated, Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from aura.api.deps import get_ollama_client, get_approval_gate, get_tool_registry
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
from aura.tools.approval import ApprovalGate
from aura.tools.registry import ToolRegistry

router = APIRouter()
logger = structlog.get_logger()


@router.post("/v1/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    ollama: Annotated[OllamaClient, Depends(get_ollama_client)],
    event_bus: Annotated[EventBus, Depends(get_event_bus)],
    config: Annotated[Settings, Depends(get_config)],
    approval_gate: Annotated[ApprovalGate, Depends(get_approval_gate)],
    tool_registry: Annotated[ToolRegistry, Depends(get_tool_registry)],
) -> Any:
    """
    OpenAI-compatible chat completion endpoint.
    Supports streaming, tool calls with approval gates, and orb state events.
    """
    request_id = f"chatcmpl-{uuid.uuid4()}"
    created_time = int(time.time())

    # Build initial message list including system prompt and context
    raw_messages = [m.model_dump(exclude_none=True) for m in request.messages]
    
    # If tools are not provided in request, use all available tools from registry
    tool_schemas = request.tools
    if not tool_schemas:
        tool_schemas = tool_registry.generate_tool_schemas()

    messages = build_messages(
        messages=raw_messages,
        tool_schemas=tool_schemas,
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
                        tools=tool_schemas,
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
                    
                    tool = tool_registry.get_tool(e.tool_name)
                    if not tool:
                        logger.error("tool_not_found", tool_name=e.tool_name)
                        messages.append({
                            "role": "assistant",
                            "content": e.partial_response
                        })
                        messages.append({
                            "role": "tool",
                            "name": e.tool_name,
                            "content": json.dumps({"error": f"Tool {e.tool_name} not found"})
                        })
                        continue

                    # 1. Approval Gate
                    approved = True
                    # Check risk level and config
                    if (tool.risk_level.value == "high" or 
                        (tool.risk_level.value == "medium" and config.require_approval_medium)):
                        
                        approved = await approval_gate.request_approval(
                            tool_name=e.tool_name,
                            description=tool.description,
                            args=e.tool_args,
                            risk_level=tool.risk_level
                        )

                    if approved:
                        # 2. Execute Tool
                        logger.info("executing_tool", tool_name=e.tool_name, args=e.tool_args)
                        await event_bus.publish("tool_call_start", {"tool_name": e.tool_name, "args": e.tool_args})
                        
                        result = await tool.execute(**e.tool_args)
                        
                        await event_bus.publish("tool_result", {
                            "tool_name": e.tool_name,
                            "success": result.success,
                            "output": result.output,
                            "error": result.error
                        })
                        
                        # 3. Inject result and resume
                        tool_call_id = str(uuid.uuid4())
                        messages.append({
                            "role": "assistant",
                            "content": e.partial_response,
                            "tool_calls": [
                                {
                                    "id": tool_call_id,
                                    "type": "function",
                                    "function": {
                                        "name": e.tool_name,
                                        "arguments": json.dumps(e.tool_args)
                                    }
                                }
                            ]
                        })
                        messages.append({
                            "role": "tool",
                            "name": e.tool_name,
                            "content": json.dumps(result.output if result.success else {"error": result.error})
                        })
                        
                        logger.info("resuming_after_tool_call", tool_name=e.tool_name)
                    else:
                        # Tool denied
                        denial_msg = f"\n[Tool call '{e.tool_name}' denied by user]"
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

    # Non-streaming implementation
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
