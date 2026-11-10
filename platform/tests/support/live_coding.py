"""Read the existing private test binding only after the caller authorizes live work."""

import os
from pathlib import Path

from pydantic import SecretStr


def live_coding_credential() -> SecretStr:
    value = os.environ.get("LUMORA_TEST_OPENAI_API_KEY", "").strip()
    path = Path(__file__).resolve().parents[1] / "infra/.state/llm/LUMORA_TEST_OPENAI_API_KEY"
    try:
        if not value and path.is_file():
            value = path.read_text().strip()
    except OSError:
        raise ValueError("Private coding test credential is unavailable") from None
    if not value:
        raise ValueError("Private coding test credential is unavailable")
    return SecretStr(value)
