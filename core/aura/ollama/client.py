import asyncio
import json
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

import httpx
import structlog

from aura.config import get_config
from aura.ollama.schemas import (
    OllamaChatChunk,
    OllamaChatRequest,
    OllamaEmbedRequest,
    OllamaEmbedResponse,
    OllamaMessage,
    OllamaPullProgress,
)

logger = structlog.get_logger()


class ToolCallDetected(Exception):
    """
    Raised when a tool call is detected in the Ollama response stream.
    """

    def __init__(self, tool_name: str, tool_args: Dict[str, Any], partial_response: str):
        super().__init__(f"Tool call detected: {tool_name}")
        self.tool_name = tool_name
        self.tool_args = tool_args
        self.partial_response = partial_response


class OllamaClient:
    """
    Async client for the internal Ollama API.
    """

    def __init__(self) -> None:
        self.config = get_config()
        self.base_url = f"http://127.0.0.1:{self.config.ollama_port}"

    async def health(self) -> bool:
        """
        Check if bundled Ollama is running and responsive.
        """
        try:
            async with httpx.AsyncClient(base_url=self.base_url) as client:
                response = await client.get("/")
                return response.status_code == 200
        except Exception as e:
            logger.debug("ollama_health_check_failed", error=str(e))
            return False

    async def stream_chat(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        images: Optional[List[str]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream tokens from POST /api/chat.
        Yields raw token strings.
        Raises ToolCallDetected when a function call is found.
        """
        # Convert dict messages to OllamaMessage models
        ollama_messages = [OllamaMessage(**m) for m in messages]
        if images and ollama_messages:
            ollama_messages[-1].images = images

        request_data = OllamaChatRequest(
            model=model,
            messages=ollama_messages,
            tools=tools,
            stream=True,
        )

        partial_response = ""

        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=None) as client:
                async with client.stream(
                    "POST", "/api/chat", json=request_data.model_dump(exclude_none=True)
                ) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        logger.error(
                            "ollama_chat_failed",
                            status_code=response.status_code,
                            error=error_text.decode(),
                        )
                        return

                    async for line in response.aiter_lines():
                        if not line:
                            continue

                        chunk_data = json.loads(line)
                        chunk = OllamaChatChunk(**chunk_data)

                        if chunk.message:
                            # Check for tool calls
                            if chunk.message.tool_calls:
                                # For now, we handle the first tool call detected
                                tool_call = chunk.message.tool_calls[0]
                                function = tool_call.get("function", {})
                                raise ToolCallDetected(
                                    function.get("name", "unknown"),
                                    function.get("arguments", {}),
                                    partial_response,
                                )

                            # Yield normal content
                            if chunk.message.content:
                                content = chunk.message.content
                                partial_response += content
                                yield content

        except ToolCallDetected:
            # Re-raise ToolCallDetected to be handled by the caller
            raise
        except Exception as e:
            logger.error("ollama_stream_chat_error", error=str(e))
            raise

    async def pull_model(self, model: str, on_progress: Callable[[Dict[str, Any]], Any]) -> None:
        """
        Download a model. Calls on_progress({ status, percent, completed, total }).
        Supports both sync and async callbacks.
        """
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=None) as client:
                async with client.stream("POST", "/api/pull", json={"name": model}) as response:
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        
                        data = json.loads(line)
                        progress = OllamaPullProgress(**data)
                        
                        # Calculate percentage if total is available
                        percent = 0
                        if progress.total and progress.completed:
                            percent = int((progress.completed / progress.total) * 100)
                        
                        payload = {
                            "status": progress.status,
                            "percent": percent,
                            "completed": progress.completed,
                            "total": progress.total
                        }
                        
                        if asyncio.iscoroutinefunction(on_progress):
                            await on_progress(payload)
                        else:
                            on_progress(payload)
        except Exception as e:
            logger.error("ollama_pull_model_error", model=model, error=str(e))
            raise

    async def list_models(self) -> List[Dict[str, Any]]:
        """
        Return all locally available models.
        """
        try:
            async with httpx.AsyncClient(base_url=self.base_url) as client:
                response = await client.get("/api/tags")
                response.raise_for_status()
                return response.json().get("models", [])
        except Exception as e:
            logger.error("ollama_list_models_error", error=str(e))
            return []

    async def delete_model(self, model: str) -> None:
        """
        Remove a model from local storage.
        """
        try:
            async with httpx.AsyncClient(base_url=self.base_url) as client:
                response = await client.request("DELETE", "/api/delete", json={"name": model})
                response.raise_for_status()
                logger.info("ollama_model_deleted", model=model)
        except Exception as e:
            logger.error("ollama_delete_model_error", model=model, error=str(e))
            raise

    async def embed(self, model: str, text: str) -> List[float]:
        """
        Generate an embedding vector via POST /api/embed.
        """
        request_data = OllamaEmbedRequest(model=model, input=text)
        try:
            async with httpx.AsyncClient(base_url=self.base_url) as client:
                response = await client.post("/api/embed", json=request_data.model_dump(exclude_none=True))
                response.raise_for_status()
                data = OllamaEmbedResponse(**response.json())
                # Return the first embedding (since we only passed one string)
                return data.embeddings[0] if data.embeddings else []
        except Exception as e:
            logger.error("ollama_embed_error", error=str(e))
            raise

    async def get_running_models(self) -> List[Dict[str, Any]]:
        """
        Return models currently loaded in memory via GET /api/ps.
        """
        try:
            async with httpx.AsyncClient(base_url=self.base_url) as client:
                response = await client.get("/api/ps")
                response.raise_for_status()
                return response.json().get("models", [])
        except Exception as e:
            logger.debug("ollama_get_running_models_failed", error=str(e))
            return []
