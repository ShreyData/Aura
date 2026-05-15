from typing import Any, Dict, List, Optional

import psutil
import structlog

from aura.ollama.client import OllamaClient

logger = structlog.get_logger()


class OllamaManager:
    """
    Orchestrates Ollama model lifecycle, hardware-aware recommendations,
    and active model status tracking.
    """

    def __init__(self, client: Optional[OllamaClient] = None) -> None:
        self.client = client or OllamaClient()

    def get_system_recommendation(self) -> Dict[str, Any]:
        """
        Determines the best Gemma 4 variant and returns system hardware context.
        """
        total_ram_gb = psutil.virtual_memory().total / (1024**3)
        cpu_count = psutil.cpu_count()
        
        if total_ram_gb < 16:
            model = "gemma4:e2b"
        elif total_ram_gb < 32:
            model = "gemma4:e4b"
        elif total_ram_gb < 64:
            model = "gemma4:26b"
        else:
            model = "gemma4:31b"
            
        return {
            "recommended_model": model,
            "total_ram_gb": round(total_ram_gb, 1),
            "cpu_count": cpu_count
        }

    def get_recommended_model(self) -> str:
        """Legacy wrapper returning just the model name."""
        return self.get_system_recommendation()["recommended_model"]

    async def ensure_model_pulled(self, model_name: str) -> None:
        """
        Checks if a model exists locally. If not, pulls it from the Ollama library.
        """
        models = await self.client.list_models()
        # model['name'] often includes the ':latest' tag if not specified
        existing_names = {m["name"] for m in models}
        
        # Check for exact match or name:latest match
        if model_name not in existing_names and f"{model_name}:latest" not in existing_names:
            logger.info("pulling_missing_model", model=model_name)
            
            def log_progress(progress: Dict[str, Any]) -> None:
                logger.info(
                    "pull_progress",
                    status=progress.get("status"),
                    percent=progress.get("percent"),
                )

            await self.client.pull_model(model_name, on_progress=log_progress)
        else:
            logger.debug("model_already_exists", model=model_name)

    async def get_model_status(self) -> Dict[str, Any]:
        """
        Returns information about the currently active (loaded) model.
        """
        running_models = await self.client.get_running_models()
        
        if not running_models:
            return {
                "active": False,
                "model": None,
                "vram_usage": 0,
            }

        # Ollama usually only has one model truly 'active' for inference at a time
        active = running_models[0]
        return {
            "active": True,
            "model": active.get("name"),
            "size_vram": active.get("size_vram", 0),
            "expires_at": active.get("expires_at"),
        }
