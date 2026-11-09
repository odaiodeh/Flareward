"""Installed catalog discovery cannot adopt unrelated process-global subclasses."""

import sys
from uuid import uuid4

import pytest
from support.elements import EchoSpec

from flareward.bootstrap.plugin_discovery import SpecDiscoverer
from plugins.testing.elements.mock_agent.spec.spec import MockAgentNodeElementSpec


def test_discovery_is_scoped_to_installed_spec_modules():
    # Both are loaded in this interpreter; only the built-in is in the discovery tree.
    specifications = SpecDiscoverer().discover()
    assert MockAgentNodeElementSpec in specifications
    assert EchoSpec not in specifications
    assert all(specification.__module__.startswith("plugins.") for specification in specifications)


def test_discovery_does_not_adopt_a_loaded_class_that_only_claims_an_installed_module():
    class ImpersonatingSpec(EchoSpec):
        __module__ = MockAgentNodeElementSpec.__module__

    assert ImpersonatingSpec not in SpecDiscoverer().discover()


@pytest.fixture
def discovery_package(tmp_path, monkeypatch):
    name = "flareward_discovery_" + uuid4().hex
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
        ("import plugins.missing_internal_module", ModuleNotFoundError),
        ("import flareward.missing_internal_module", ModuleNotFoundError),
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
    source.write_text("import flareward_optional_dependency_that_is_not_installed")
    assert SpecDiscoverer(root, package=name).discover() == []


def test_explicit_optional_modules_use_the_same_scoped_discovery(discovery_package):
    name, root, source = discovery_package
    source.write_text("import flareward_optional_dependency_that_is_not_installed")
    assert SpecDiscoverer(root, package=name).discover_modules([f"{name}.tools.example.spec"]) == []


def test_abstract_spec_bases_are_not_discovered_but_concrete_descendants_are(discovery_package):
    name, root, source = discovery_package
    source.write_text(
        "from support.elements import DependencySpec\n"
        "class SharedBase(DependencySpec, abstract=True):\n    pass\n"
        "class Concrete(SharedBase):\n    pass\n"
    )
    found = SpecDiscoverer(root, package=name).discover()
    assert [specification.__name__ for specification in found] == ["Concrete"]
    assert not found[0].is_abstract


def test_graph_contract_module_has_no_installable_base_specifications():
    assert SpecDiscoverer().discover_modules(["flareward.programs.graph_elements"]) == []
