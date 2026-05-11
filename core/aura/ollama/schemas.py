from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class OllamaMessage(BaseModel):
    """
    Represents a single message in an Ollama chat conversation.
    """

    role: str
    content: str
    images: Optional[List[str]] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


class OllamaChatRequest(BaseModel):
    """
    Request body for POST /api/chat.
    """

    model: str
    messages: List[OllamaMessage]
    tools: Optional[List[Dict[str, Any]]] = None
    format: Optional[str] = None
    options: Optional[Dict[str, Any]] = None
    stream: bool = True
    keep_alive: Optional[Union[str, int]] = None


class OllamaChatChunk(BaseModel):
    """
    A single NDJSON chunk returned by /api/chat when streaming.
    """

    model: str
    created_at: datetime
    message: Optional[OllamaMessage] = None
    done: bool
    done_reason: Optional[str] = None
    total_duration: Optional[int] = None
    load_duration: Optional[int] = None
    prompt_eval_count: Optional[int] = None
    prompt_eval_duration: Optional[int] = None
    eval_count: Optional[int] = None
    eval_duration: Optional[int] = None


class OllamaModelDetails(BaseModel):
    """
    Specific metadata about an Ollama model.
    """

    parent_model: str = ""
    format: str = ""
    family: str = ""
    families: Optional[List[str]] = None
    parameter_size: str = ""
    quantization_level: str = ""


class OllamaModelInfo(BaseModel):
    """
    Represents a model returned by GET /api/tags.
    """

    name: str
    model: str
    modified_at: datetime
    size: int
    digest: str
    details: OllamaModelDetails


class OllamaPullProgress(BaseModel):
    """
    A single NDJSON chunk returned by /api/pull.
    """

    status: str
    digest: Optional[str] = None
    total: Optional[int] = None
    completed: Optional[int] = None


class OllamaEmbedRequest(BaseModel):
    """
    Request body for POST /api/embed.
    Note: Ollama recently unified /api/embeddings into /api/embed.
    """

    model: str
    input: Union[str, List[str]]
    options: Optional[Dict[str, Any]] = None
    keep_alive: Optional[Union[str, int]] = None


class OllamaEmbedResponse(BaseModel):
    """
    Response body for POST /api/embed.
    """

    model: str
    embeddings: List[List[float]]
    total_duration: int
    load_duration: int
    prompt_eval_count: int
