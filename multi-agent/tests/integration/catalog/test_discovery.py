"""Installed catalog discovery cannot adopt unrelated process-global subclasses."""

import sys
from uuid import uuid4

import pytest
from mas.elements.nodes.mock_agent.spec.spec import MockAgentNodeElementSpec
from outbound.elements.discovery import SpecDiscoverer
from support.elements import EchoSpec


def test_discovery_is_scoped_to_installed_spec_modules():
    # Both are loaded in this interpreter; only the built-in is in the discovery tree.
    specifications = SpecDiscoverer().discover()
    assert MockAgentNodeElementSpec in specifications
    assert EchoSpec not in specifications
    assert all(
        specification.__module__.startswith("mas.elements.") for specification in specifications
    )


def test_discovery_does_not_adopt_a_loaded_class_that_only_claims_an_installed_module():
    class ImpersonatingSpec(EchoSpec):
        __module__ = MockAgentNodeElementSpec.__module__

    assert ImpersonatingSpec not in SpecDiscoverer().discover()


@pytest.fixture
def discovery_package(tmp_path, monkeypatch):
    name = "unifai_discovery_" + uuid4().hex
    root = tmp_path / name
    specification = root / "tools" / "example" / "spec"
    specification.mkdir(parents=True)
    for directory in (root, root / "tools", root / "tools/example"):
        (directory / "__init__.py").write_text("")
    monkeypatch.syspath_prepend(str(tmp_path))
    try:
        yield name, root, specification / "__init__.py"
    finally:
        for module in tuple(sys.modules):
            if module == name or module.startswith(name + "."):
                sys.modules.pop(module)


@pytest.mark.parametrize(
    "code,exception",
    [
        ("from .missing_internal import value", ModuleNotFoundError),
        ("raise ImportError('Incompatible installed SDK', name='dependency')", ImportError),
        ("raise ValueError('Invalid plugin declaration')", ValueError),
    ],
)
def test_broken_installed_plugins_fail_discovery_instead_of_disappearing(
    discovery_package,
    code,
    exception,
):
    name, root, source = discovery_package
    source.write_text(code)
    with pytest.raises(exception):
        SpecDiscoverer(root, package=name).discover()


def test_an_uninstalled_optional_dependency_keeps_its_adapter_unavailable(discovery_package):
    name, root, source = discovery_package
    source.write_text("import unifai_optional_dependency_that_is_not_installed")
    assert SpecDiscoverer(root, package=name).discover() == []
