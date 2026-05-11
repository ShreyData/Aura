import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Tuple, Type

from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)


class Settings(BaseSettings):
    """
    Aura configuration settings managed via pydantic-settings.
    Loads values from environment variables (AURA_*) and ~/.aura/config.toml.
    """

    core_port: int = 11434
    ollama_port: int = 11435
    ollama_models_dir: str = str(Path.home() / ".aura" / "models")
    default_model: str = "gemma:2b"
    embed_model: str = "nomic-embed-text"
    workspace_path: Path = (
        Path.home() / "Documents" / "AuraWorkspace"
        if sys.platform in ("win32", "darwin")
        else Path.home() / "AuraWorkspace"
    )
    allow_system_paths: bool = False
    require_approval_medium: bool = True
    log_level: str = "INFO"
    auto_unload_minutes: int = 5

    model_config = SettingsConfigDict(
        env_prefix="AURA_",
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        """
        Define the priority of configuration sources:
        1. Environment variables (AURA_*)
        2. User config (~/.aura/config.toml)
        3. Project defaults (shared/config/defaults.toml)
        4. Hardcoded defaults in this class
        """
        user_config_path = Path.home() / ".aura" / "config.toml"
        project_defaults_path = (
            Path(__file__).parent.parent.parent / "shared" / "config" / "defaults.toml"
        )

        sources: list[PydanticBaseSettingsSource] = [init_settings, env_settings]

        if user_config_path.exists():
            sources.append(TomlConfigSettingsSource(settings_cls, toml_file=user_config_path))

        if project_defaults_path.exists():
            sources.append(TomlConfigSettingsSource(settings_cls, toml_file=project_defaults_path))

        return tuple(sources)


@lru_cache()
def get_config() -> Settings:
    """
    Returns a cached singleton instance of the Settings.
    """
    return Settings()
