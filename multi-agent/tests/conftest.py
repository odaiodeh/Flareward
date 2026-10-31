"""Application fixtures are available without constructing infrastructure."""

import os
from pathlib import Path

import pytest
from pydantic import SecretStr
from support.application import Application, make_application


@pytest.fixture
def application() -> Application:
    return make_application()


def pytest_addoption(parser):
    parser.addoption(
        "--ui-clients",
        action="store_true",
        default=False,
        help="Run real TypeScript API client integration",
    )
    parser.addoption(
        "--live-coding",
        action="store_true",
        default=False,
        help="Explicitly allow bounded paid Codex coding-agent tests",
    )


@pytest.fixture
def live_coding_key(request):
    if not request.config.getoption("--live-coding"):
        pytest.skip("Select --live-coding to allow real paid coding-agent calls")
    if not request.config.getoption("--platform-backends", default=""):
        pytest.fail("Live coding requires an explicit --platform-backends selection", pytrace=False)
    key_path = Path(__file__).parent / "infra/.state/llm/UNIFAI_TEST_OPENAI_API_KEY"
    value = os.environ.get("UNIFAI_TEST_OPENAI_API_KEY", "")
    if not value and key_path.is_file():
        value = key_path.read_text().strip()
    if not value:
        pytest.fail("Live coding tests require a private OpenAI test credential", pytrace=False)
    return SecretStr(value)
