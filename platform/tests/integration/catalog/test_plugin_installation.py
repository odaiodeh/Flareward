"""A capability can contribute Elements and Programs without changing either registry."""

import pytest

from flareward.bootstrap.elements import installed_elements
from flareward.bootstrap.plugins import installed_plugins
from flareward.bootstrap.programs import installed_applications
from flareward.resources.domain.categories import ResourceCategory

PLUGIN = "plugins.human_review.plugin"


def test_one_plugin_contributes_to_both_existing_catalogs():
    plugins = (PLUGIN, PLUGIN)
    assert len(installed_plugins(plugins)) == 1
    elements = installed_elements(plugins=plugins)
    assert (
        elements.get_spec(ResourceCategory.PROVIDER, "review_service").type_key == "review_service"
    )
    programs = installed_applications(plugins=plugins)
    assert programs.get("human_review", "1").config_schema is not None
    assert programs.get("repeat", "1").execute is not None
    with pytest.raises(ValueError, match="not installed"):
        installed_applications().get("human_review", "1")
    assert not installed_elements(plugins=()).get_categories_map()
