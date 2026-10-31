"""Read portable authoring input; application services validate installed element schemas."""

from pathlib import Path

import yaml
from mas.blueprints.contracts import BlueprintData
from pydantic import TypeAdapter, ValidationError

_DOCUMENT = TypeAdapter(BlueprintData)


def parse_blueprint(content: str | bytes) -> BlueprintData:
    try:
        return _DOCUMENT.validate_python(yaml.safe_load(content))
    except (yaml.YAMLError, ValidationError, UnicodeError):
        raise ValueError("Blueprint must contain a YAML or JSON object") from None


class BlueprintFileLoader:
    def load(self, path: str) -> BlueprintData:
        try:
            content = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            raise ValueError("Blueprint file cannot be read") from None
        return parse_blueprint(content)
