from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict

import json
import yaml
from dotenv import dotenv_values


class ConfigSource(ABC):
    """
    Abstract base for all configuration sources.
    """

    @abstractmethod
    def load(self) -> Dict[str, Any]:
        ...


class DotEnvSource(ConfigSource):
    """
    Loads key/value pairs from a .env file in the current working directory.
    """

    def __init__(self, path: str = ".env"):
        self._path = Path(path)

    def load(self) -> Dict[str, Any]:
        if not self._path.exists():
            return {}
        return dotenv_values(self._path)


class YamlSource(ConfigSource):
    """
    Loads configuration from a config.yaml file in the current working directory.
    """

    def __init__(self, path: str = "config.yaml"):
        self._path = Path(path)

    def load(self) -> Dict[str, Any]:
        if not self._path.exists():
            return {}
        data = yaml.safe_load(self._path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}


class JsonSource(ConfigSource):
    """
    Loads configuration from a config.json file in the current working directory.
    """

    def __init__(self, path: str = "config.json"):
        self._path = Path(path)

    def load(self) -> Dict[str, Any]:
        if not self._path.exists():
            return {}
        data = json.loads(self._path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
