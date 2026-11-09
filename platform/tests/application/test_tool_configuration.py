"""Tool-executor construction borrows its ports and snapshots its collection of validators."""

from unittest.mock import create_autospec

from flareward.elements.tools.config import ExecutorConfig
from flareward.elements.tools.interfaces import ErrorHandler, ExecutionValidator


def test_executor_configuration_passes_original_ports_without_cloning_their_resources():
    handler = create_autospec(ErrorHandler, instance=True)
    validator = create_autospec(ExecutionValidator, instance=True)
    validators = [validator]
    arguments = ExecutorConfig(error_handler=handler, validators=validators).to_dict()
    assert arguments["error_handler"] is handler
    assert arguments["validators"][0] is validator
    validators.clear()
    assert arguments["validators"] == [validator]
    assert "default_timeout" not in arguments
