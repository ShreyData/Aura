from functools import lru_cache
from typing import Generator

from aura.ollama.client import OllamaClient
from aura.ollama.manager import OllamaManager


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
