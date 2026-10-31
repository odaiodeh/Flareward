"""Guard dependency direction, native async boundaries, and independent test layers."""

import ast
import subprocess
import sys
from collections.abc import Iterator
from importlib.util import resolve_name
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SDK_ROOTS = frozenset(
    {
        "runengine",
        "run_engine",
        "fastapi",
        "flask",
        "temporalio",
        "kubernetes",
        "pymongo",
        "cryptography",
        "langfuse",
        "opentelemetry",
    }
)

ELEMENT_SDK_ROOTS = SDK_ROOTS | {
    "mcp",
    "a2a",
    "openai",
    "google",
    "langchain",
    "langchain_core",
    "langgraph",
    "deepagents",
    "claude_agent_sdk",
    "openshell",
    "paramiko",
    "openshift_client",
    "httpx",
    "httpx2",
    "aiohttp",
    "requests",
    "global_utils",
}


def imported_modules(path: Path) -> Iterator[str]:
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            yield node.module or ""


def layer_imports(path: Path) -> Iterator[str]:
    parts = path.relative_to(ROOT / "lib").with_suffix("").parts
    package = ".".join(parts[:-1])
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            name = node.module or ""
            if node.level:
                name = resolve_name("." * node.level + name, package)
            yield name
            yield from (name + "." + alias.name for alias in node.names)


def test_shared_agent_layers_depend_inward_and_do_not_import_plugins_or_transports():
    for layer in ("domain", "application"):
        paths = list((ROOT / "lib/mas" / layer).rglob("*.py"))
        assert paths, layer
        for path in paths:
            for name in layer_imports(path):
                assert name.split(".")[0] not in ELEMENT_SDK_ROOTS, (path, name)
                assert not name.startswith(
                    ("mas.elements", "inbound", "outbound", "bootstrap", "config")
                ), (path, name)
                if layer == "domain" and name.startswith("mas."):
                    # Existing canonical identity/discriminator values are SDK-free domain data.
                    assert name.startswith(("mas.domain", "mas.core.enums", "mas.core.identity")), (
                        path,
                        name,
                    )


def test_cold_shared_agent_imports_do_not_load_plugins_or_global_infrastructure_settings():
    check = """
import sys
from mas.application.capabilities.agent_capable import AgentCapableMixin
from mas.application.agents.strategies.react import ReActStrategy
from mas.application.elements.condition import BaseCondition
from mas.application.elements.condition_config import BaseConditionConfig
from mas.application.tools.validators import ArgumentValidator
from mas.domain.workloads import Workspace
blocked = ('mas.elements', 'global_utils', 'inbound', 'outbound', 'bootstrap',
           'flask', 'fastapi', 'temporalio', 'runengine', 'mcp', 'a2a', 'openai',
           'google.genai', 'langchain', 'pymongo', 'httpx', 'openshell')
assert not [name for name in sys.modules if name.startswith(blocked)]
"""
    completed = subprocess.run([sys.executable, "-c", check], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr


def test_application_services_do_not_import_execution_or_http_adapters():
    paths = [
        path
        for package in (
            "programs",
            "execution",
            "interactions",
            "application/elements/construction",
            "application/collaboration",
            "application/actions",
            "application/sharing",
            "core/auth",
            "core/tracing",
            "validation",
            "graph/validation",
        )
        for path in (ROOT / "lib/mas" / package).rglob("*.py")
    ]
    paths.extend(
        ROOT / "lib/mas/session/execution" / name
        for name in (
            "program_sessions.py",
            "blueprint_sessions.py",
            "queries.py",
            "staging.py",
            "session_store.py",
        )
    )
    paths.append(ROOT / "lib/mas/core/secrets.py")
    paths.append(ROOT / "lib/mas/core/execution_preferences.py")
    paths.append(ROOT / "lib/mas/application/elements/validation.py")
    paths.append(ROOT / "lib/mas/graph/analysis.py")
    paths.extend(ROOT / "lib/mas/scheduling" / name for name in ("programs.py", "admission.py"))
    paths.extend(
        ROOT / "lib/mas/resources" / name
        for name in (
            "authoring.py",
            "access.py",
            "field_encryption.py",
            "models.py",
            "inspection.py",
            "resolver.py",
        )
    )
    paths.extend(
        ROOT / "lib/mas/blueprints" / name
        for name in (
            "authoring.py",
            "contracts.py",
            "metadata.py",
            "queries.py",
            "placement.py",
            "inspection.py",
            "collector.py",
            "resolution.py",
            "resolver.py",
            "schema.py",
        )
    )
    for path in paths:
        assert not any(
            name.split(".")[0] in SDK_ROOTS | {"inbound", "outbound"}
            for name in imported_modules(path)
        ), path


def test_platform_imports_stay_at_module_scope_and_use_no_async_bridge():
    paths = [
        path
        for directory in (
            "lib/mas/programs",
            "lib/mas/domain",
            "lib/mas/application",
            "lib/mas/execution",
            "lib/mas/application/elements/construction",
            "lib/mas/interactions",
            "lib/mas/core/auth",
            "lib/mas/core/tracing",
            "lib/mas/validation",
            "lib/mas/graph/validation",
            "adapters/outbound/interactions",
            "adapters/outbound/auth",
            "adapters/outbound/actions",
            "adapters/outbound/langfuse",
            "adapters/run_engine",
            "adapters/inbound/run_engine",
            "adapters/outbound/run_engine",
            "adapters/inbound/http_api",
        )
        for path in (ROOT / directory).rglob("*.py")
    ]
    paths.extend(
        ROOT / "bootstrap" / name
        for name in (
            "platform.py",
            "actions.py",
            "asgi.py",
            "http_cli.py",
            "receiver.py",
            "credentials.py",
            "worker.py",
            "library.py",
            "tracing.py",
        )
    )
    paths.extend(
        ROOT / "lib/mas/session/execution" / name
        for name in (
            "program_sessions.py",
            "blueprint_sessions.py",
            "queries.py",
            "session_store.py",
        )
    )
    paths.append(ROOT / "lib/mas/core/secrets.py")
    paths.append(ROOT / "lib/mas/core/execution_preferences.py")
    paths.append(ROOT / "lib/mas/application/elements/validation.py")
    paths.append(ROOT / "lib/mas/graph/analysis.py")
    paths.extend(ROOT / "lib/mas/scheduling" / name for name in ("programs.py", "admission.py"))
    paths.extend(
        ROOT / "lib/mas/resources" / name
        for name in (
            "authoring.py",
            "access.py",
            "field_encryption.py",
            "models.py",
            "inspection.py",
            "resolver.py",
        )
    )
    paths.extend(
        ROOT / "lib/mas/blueprints" / name
        for name in (
            "authoring.py",
            "contracts.py",
            "metadata.py",
            "queries.py",
            "placement.py",
            "inspection.py",
            "collector.py",
            "resolution.py",
            "resolver.py",
            "schema.py",
        )
    )
    for path in paths:
        source = path.read_text()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                assert not any(
                    isinstance(child, (ast.Import, ast.ImportFrom)) for child in ast.walk(node)
                ), path
        assert "asyncio.run(" not in source and "async_bridge" not in source, path


def test_cold_application_imports_do_not_load_legacy_runners_or_vendor_clients():
    import_check = """
import sys
from mas.session.execution.program_sessions import ProgramSessionService
from mas.programs.blueprints import BlueprintProgramImporter
from mas.blueprints.authoring import BlueprintAuthoringService
from mas.blueprints.schema import blueprint_schemas
from mas.blueprints.resolver import BlueprintResolver
from mas.blueprints.inspection import BlueprintInspectionService
from mas.blueprints.placement import BlueprintPlacementService
from mas.execution.placement import GraphPlacementPreviewer
from mas.application.collaboration.editing import TeamEditService
from mas.application.actions.service import ActionsService
from mas.application.actions.auth.discovery.action import DiscoveryAction
from mas.application.actions.auth.store_credential.action import StoreCredentialAction
from mas.application.sharing.notifications import ShareNotifications
from mas.domain.sharing import ShareInvite
from mas.resources.authoring import ResourceAuthoringService
from mas.validation.service import ElementValidationService
from mas.graph.analysis import BlueprintGraphAnalysisService
from mas.scheduling.programs import ProgramScheduleService
for name in (
    'flask', 'temporalio', 'a2a', 'mcp', 'langgraph', 'openai', 'langfuse', 'opentelemetry.sdk'
):
    assert name not in sys.modules, name
"""
    completed = subprocess.run([sys.executable, "-c", import_check], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr


def test_native_telemetry_adapter_does_not_require_the_legacy_langfuse_sdk():
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from outbound.langfuse import otel; assert 'langfuse' not in sys.modules",
        ],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_native_library_composition_does_not_load_closed_vendor_configuration_lists():
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import bootstrap.library; "
            "assert 'mas.blueprints.models.blueprint' not in sys.modules; "
            "assert 'mas.elements.nodes.types' not in sys.modules; "
            "assert 'mas.elements.llms.types' not in sys.modules",
        ],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_application_tests_and_support_do_not_import_engine_or_http():
    paths = list((ROOT / "tests/application").rglob("*.py"))
    paths.extend(
        ROOT / "tests/support" / name
        for name in (
            "application.py",
            "elements.py",
            "conditions.py",
            "condition_scenarios.py",
            "programs.py",
            "scenarios.py",
            "credentials.py",
            "approval.py",
            "secrets.py",
            "blueprints.py",
            "inspection.py",
            "resolution.py",
            "remote.py",
            "remote_scenarios.py",
            "scheduling.py",
            "tracing_elements.py",
            "agent_session.py",
            "agent_session_assertions.py",
        )
    )
    for path in paths:
        assert not any(
            name.split(".")[0] in SDK_ROOTS | {"inbound", "pymongo"}
            or name.startswith("outbound.run_engine")
            for name in imported_modules(path)
        ), path


def test_tests_share_support_without_importing_other_test_cases():
    for path in (ROOT / "tests").rglob("*.py"):
        assert not any(
            part.startswith("test_") for name in imported_modules(path) for part in name.split(".")
        ), path
