"""The retained CLI loader returns portable data and closes files before validation."""

import pytest

from lumora.programs.templates.input.files import BlueprintFileLoader


@pytest.mark.parametrize(
    "content", ['{"name": "Blueprint", "plan": []}', "name: Blueprint\nplan: []\n"]
)
def test_json_and_yaml_share_the_same_portable_loader(tmp_path, content):
    path = tmp_path / "blueprint"
    path.write_text(content)
    assert BlueprintFileLoader().load(str(path)) == {"name": "Blueprint", "plan": []}
    path.unlink()


@pytest.mark.parametrize("content", ["- private-value", "value: [private-value"])
def test_invalid_files_do_not_echo_private_values(tmp_path, content):
    path = tmp_path / "invalid"
    path.write_text(content)
    with pytest.raises(ValueError) as raised:
        BlueprintFileLoader().load(str(path))
    assert "private-value" not in str(raised.value)
