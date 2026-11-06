"""Application fixtures are available without constructing infrastructure."""

import pytest
from support.application import Application, make_application
from support.coding_cli import codex_cli as codex_cli
from support.live_coding import live_coding_credential
from support.repositories import local_repository as local_repository


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
    parser.addoption(
        "--strict-sandbox-filesystem",
        action="store_true",
        default=False,
        help="Additionally require Landlock filesystem enforcement on a capable Linux host",
    )


@pytest.fixture
def live_coding_key(request):
    if not request.config.getoption("--live-coding"):
        pytest.skip("Select --live-coding to allow real paid coding-agent calls")
    if not request.config.getoption("--platform-backends", default=""):
        pytest.fail("Live coding requires an explicit --platform-backends selection", pytrace=False)
    try:
        return live_coding_credential()
    except ValueError:
        pytest.fail("Live coding tests require a private OpenAI test credential", pytrace=False)
