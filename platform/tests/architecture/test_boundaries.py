"""Enforce feature-local hexagons, plugin independence and canonical installed paths."""

import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src"
CORE = SOURCE / "lumora"
PLUGINS = SOURCE / "plugins"
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
        "openai",
        "google",
        "mcp",
        "a2a",
        "httpx",
        "redis",
        "requests",
        "langchain",
        "langchain_core",
        "langgraph",
        "deepagents",
        "claude_agent_sdk",
        "openshell",
        "global_utils",
    }
)


def imports(path):
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            yield node.module or ""


def cold(code):
    completed = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr


def test_source_layout_has_one_canonical_platform_and_plugin_namespace():
    assert sorted(p.name for p in SOURCE.iterdir() if p.is_dir() and p.name != "__pycache__") == [
        "lumora",
        "plugins",
    ]
    for retired in ("lib", "adapters", "plugins", "bootstrap", "config"):
        assert not (ROOT / retired).exists()
    cold(
        "from importlib.util import find_spec; assert find_spec('mas') is None; "
        "assert find_spec('mas_plugins') is None; assert find_spec('flareward') is None"
    )


def test_core_behavior_does_not_import_plugins_or_technology_adapters():
    paths = [
        p for p in CORE.rglob("*.py") if not {"adapters", "api", "bootstrap"}.intersection(p.parts)
    ]
    assert paths
    for path in paths:
        for name in imports(path):
            assert name.split(".")[0] not in SDK_ROOTS, (path, name)
            assert not name.startswith("plugins"), (path, name)
            assert not name.startswith(("lumora.api", "lumora.bootstrap")), (path, name)
            assert ".adapters." not in name, (path, name)


def test_feature_domain_values_do_not_depend_on_services_or_installed_implementations():
    paths = [p for p in CORE.rglob("*.py") if "domain" in p.relative_to(CORE).parts]
    assert paths
    for path in paths:
        for name in imports(path):
            assert name.split(".")[0] not in SDK_ROOTS, (path, name)
            assert not name.startswith("plugins"), (path, name)
            if name.startswith("lumora."):
                assert ".domain" in name or name in {"lumora.models", "lumora.json_values"}, (
                    path,
                    name,
                )


def test_plugin_domains_do_not_import_transport_or_coordination_sdks():
    for path in PLUGINS.rglob("*.py"):
        if "domain" not in path.relative_to(PLUGINS).parts:
            continue
        for name in imports(path):
            assert name.split(".")[0] not in SDK_ROOTS, (path, name)
            assert ".adapters." not in name, (path, name)


def test_generic_element_construction_does_not_initialize_graph_or_plugins():
    cold("""
import sys
from lumora.elements.operation import BaseOperation, OperationContext, OperationInvoker
from lumora.elements.specification import BaseElementSpec
from lumora.elements.catalog.element_registry import ElementRegistry
from lumora.elements.construction.builder import ElementBundleBuilder
ElementBundleBuilder(ElementRegistry())
assert not hasattr(BaseElementSpec, 'reads') and not hasattr(BaseElementSpec, 'writes')
blocked = ('plugins', 'lumora.programs.graph', 'runengine', 'temporalio', 'fastapi', 'pymongo', 'global_utils')
assert not [name for name in sys.modules if name.startswith(blocked)]
""")


def test_reusable_agent_and_workload_behavior_is_graph_independent():
    cold("""
import sys
from lumora.elements.behaviors.agent_capable import AgentCapableMixin
from lumora.elements.agents.strategies.react import ReActStrategy
from lumora.elements.workloads.domain import Workspace
blocked = ('lumora.programs.graph', 'plugins', 'runengine', 'temporalio', 'global_utils')
assert not [name for name in sys.modules if name.startswith(blocked)]
""")


def test_program_domain_round_trip_needs_no_runtime_or_application_services():
    cold("""
import sys
from lumora.services.identity.domain import Identity
from lumora.programs.domain.models import CustomCoordinatorDefinition, ProgramDefinition, ProgramRevision
from lumora.programs.domain.interfaces import CoordinatorIdentity, ProgramInterface
value = ProgramRevision(definition=ProgramDefinition(program_id='test', name='Test',
    owner=Identity.user('owner'), implementation=CustomCoordinatorDefinition(implementation='registered', version='1')), revision=1, interface=ProgramInterface(coordinator=CoordinatorIdentity(key='registered', version='1'), input_schema={'type':'object'}, output_schema={'type':'object'}))
assert ProgramRevision.model_validate_json(value.model_dump_json()) == value
blocked = ('lumora.bootstrap', 'lumora.api', 'plugins', 'runengine', 'temporalio', 'pymongo')
assert not [name for name in sys.modules if name.startswith(blocked)]
""")


def test_execution_values_do_not_initialize_runtime_holders_or_infrastructure():
    cold("""
import sys
from lumora.services.identity.domain import Identity
from lumora.executions.domain.context import ExecutionContext
from lumora.executions.domain.models import ExecutionRecord
from lumora.programs.domain.models import ProgramRef
context = ExecutionContext(identity=Identity.user('owner'), execution_id='root')
record = ExecutionRecord(execution_id='root', owner=context.identity,
    program=ProgramRef(program_id='program', revision=1), inputs={}, context=context)
assert ExecutionRecord.model_validate_json(record.model_dump_json()) == record
blocked = ('lumora.executions.context', 'lumora.bootstrap', 'lumora.api', 'plugins', 'runengine', 'pymongo')
assert not [name for name in sys.modules if name.startswith(blocked)]
""")


def test_all_production_imports_are_at_module_scope():
    for path in SOURCE.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                assert not any(
                    isinstance(child, (ast.Import, ast.ImportFrom)) for child in ast.walk(node)
                ), path


def test_feature_behavior_uses_no_nested_event_loop_or_async_bridge():
    for path in CORE.rglob("*.py"):
        if path.name == "http_cli.py":
            continue
        text = path.read_text()
        assert "asyncio.run(" not in text and "async_bridge" not in text, path


def test_registered_plugins_have_feature_owned_manifests():
    cold("""
from lumora.bootstrap.plugins import installed_plugins
from lumora.bootstrap.settings.plugins import DEFAULT_PLUGINS
plugins = installed_plugins(DEFAULT_PLUGINS)
assert plugins and len({plugin.key for plugin in plugins}) == len(plugins)
assert any(plugin.elements and plugin.programs for plugin in plugins)
""")


def test_native_startup_does_not_import_retired_runners():
    cold("""
import sys
from lumora.bootstrap.http_cli import app
assert not [name for name in sys.modules if name.startswith(('flask', 'langgraph', 'mas.engine'))]
""")


def test_native_library_composition_does_not_load_closed_vendor_unions():
    cold("""
import sys
import lumora.bootstrap.library
assert 'lumora.programs.templates.models.blueprint' not in sys.modules
assert not [name for name in sys.modules if name.startswith(('openai', 'google.genai', 'langgraph'))]
""")


def test_native_telemetry_does_not_require_legacy_langfuse_client():
    cold(
        "import sys; from lumora.services.tracing.adapters.langfuse import otel; assert 'langfuse' not in sys.modules"
    )


def test_application_tests_do_not_import_engine_or_http_sdks():
    for path in (ROOT / "tests/application").rglob("*.py"):
        assert not any(
            name.split(".")[0] in {"runengine", "fastapi", "httpx", "temporalio"}
            for name in imports(path)
        ), path


def test_programs_share_generic_data_state():
    cold("""
from lumora.programs.state import ProgramState
assert set(ProgramState.model_fields) == {'input', 'results', 'values', 'output'}
""")
