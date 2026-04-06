from pathlib import Path
from typing import Any, Dict

import yaml

from api.config import settings


def load_yaml_config(path: str) -> Dict[str, Any]:
    config_path = Path(path)
    if not config_path.is_absolute():
        config_path = Path(__file__).resolve().parent / path
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def resolve_model_registry() -> Dict[str, Any]:
    return load_yaml_config(settings.model_registry_path)


def resolve_preset_registry() -> Dict[str, Any]:
    return load_yaml_config(settings.preset_registry_path)


__all__ = ["settings", "load_yaml_config", "resolve_model_registry", "resolve_preset_registry"]
