from functools import lru_cache

from fastapi import Request

from aura.ollama.client import OllamaClient
from aura.ollama.manager import OllamaManager
from aura.events import EventBus
from aura.tools.approval import ApprovalGate
from aura.tools.registry import ToolRegistry


@lru_cache()
def get_ollama_client() -> OllamaClient:
    """
    Dependency to get a singleton OllamaClient.
    """
    return OllamaClient()


@lru_cache()
def get_ollama_manager() -> OllamaManager:
    """
    Dependency to get a singleton OllamaManager.
    """
    return OllamaManager(client=get_ollama_client())


def get_event_bus(request: Request) -> EventBus:
    """
    Dependency to get the EventBus singleton from app state.
    """
    return request.app.state.event_bus


def get_approval_gate(request: Request) -> ApprovalGate:
    """
    Dependency to get the ApprovalGate singleton from app state.
    """
    return request.app.state.approval_gate


def get_tool_registry(request: Request) -> ToolRegistry:
    """
    Dependency to get the ToolRegistry singleton from app state.
    """
    return request.app.state.tool_registry
