from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


# --- OpenAI Compatible Models ---


class ChatMessage(BaseModel):
    """
    OpenAI-compatible chat message model.
    """

    role: str
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


class ChatCompletionRequest(BaseModel):
    """
    OpenAI-compatible chat completion request body.
    """

    model: str
    messages: List[ChatMessage]
    stream: bool = False
    temperature: Optional[float] = 1.0
    top_p: Optional[float] = 1.0
    n: Optional[int] = 1
    max_tokens: Optional[int] = None
    stop: Optional[Union[str, List[str]]] = None
    presence_penalty: Optional[float] = 0.0
    frequency_penalty: Optional[float] = 0.0
    logit_bias: Optional[Dict[str, float]] = None
    user: Optional[str] = None
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None


class ChatCompletionResponseChoice(BaseModel):
    """
    A single choice in a ChatCompletionResponse.
    """

    index: int
    message: ChatMessage
    finish_reason: Optional[str] = None


class ChatCompletionUsage(BaseModel):
    """
    Usage statistics for a chat completion.
    """

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    """
    OpenAI-compatible chat completion response body.
    """

    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionResponseChoice]
    usage: Optional[ChatCompletionUsage] = None


class ChatCompletionChunkDelta(BaseModel):
    """
    The delta field in a chat completion chunk.
    """

    role: Optional[str] = None
    content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


class ChatCompletionChunkChoice(BaseModel):
    """
    A single choice in a ChatCompletionChunk.
    """

    index: int
    delta: ChatCompletionChunkDelta
    finish_reason: Optional[str] = None


class ChatCompletionChunk(BaseModel):
    """
    OpenAI-compatible chat completion chunk for SSE streaming.
    """

    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: List[ChatCompletionChunkChoice]


# --- Aura Specific Models ---


class HealthResponse(BaseModel):
    """
    System health status response.
    """

    aura: bool
    ollama: bool
    active_model: Optional[str] = None
    uptime_s: int


class PendingToolCall(BaseModel):
    """
    Represents a tool call awaiting user approval.
    """

    request_id: str
    tool_name: str
    args: Dict[str, Any]
    risk_level: str


class ToolApprovalRequest(BaseModel):
    """
    Request body for approving or denying a pending tool call.
    """

    request_id: str
    approved: bool
