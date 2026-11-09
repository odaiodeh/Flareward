"""

Makes it easy to import key classes from storage's submodules
"""

from .manager import ConfigManager
from .config import SharedConfig

__all__ = [
    "ConfigManager",
    "SharedConfig"
]
