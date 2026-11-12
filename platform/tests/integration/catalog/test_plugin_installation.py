"""A capability can contribute Elements and Programs without changing either registry."""

import pytest

from lumora.bootstrap.elements import installed_elements
from lumora.bootstrap.plugins import installed_plugins
from lumora.bootstrap.programs import installed_coordinators
from lumora.programs.registry import CustomCoordinatorStrategy, NativeGraphStrategy
from lumora.resources.domain.categories import ResourceCategory

PLUGIN = "plugins.human_review.plugin"


def test_one_plugin_contributes_to_both_existing_catalogs():
    plugins = (PLUGIN, PLUGIN)
    assert len(installed_plugins(plugins)) == 1
    elements = installed_elements(plugins=plugins)
    assert (
        elements.get_spec(ResourceCategory.PROVIDER, "review_service").type_key == "review_service"
    )
    programs = installed_coordinators(plugins=plugins)
    assert programs.get("human_review", "1").config_schema is not None
    assert isinstance(programs.get("repeat", "1").strategy, CustomCoordinatorStrategy)
    assert isinstance(programs.get("graph", "1").strategy, NativeGraphStrategy)
    with pytest.raises(ValueError, match="not installed"):
        installed_coordinators().get("human_review", "1")
    assert not installed_elements(plugins=()).get_categories_map()
