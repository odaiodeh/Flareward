"""Legacy authoring data and existing mock factories with caller-configurable metadata."""

from pydantic import Field

from lumora.elements.catalog.element_registry import ElementRegistry
from lumora.elements.hints import ReadOnlyHint, SecretHint
from lumora.programs.templates.models.blueprint import BlueprintDraft
from plugins.testing.elements.mock.config import MockLLMConfig
from plugins.testing.elements.mock.spec.spec import MockLLMElementSpec
from plugins.testing.elements.mock_agent.spec.spec import MockAgentNodeElementSpec

__runengine_contract__ = "lumora-test-blueprints-v1"


class OverlayMockConfig(MockLLMConfig):
    api_key: str = Field(
        default="EMPTY",
        json_schema_extra={
            "hints": {
                **SecretHint().to_hints()["hints"],
                **ReadOnlyHint(read_only=False).to_hints()["hints"],
            }
        },
    )


class OverlayMockSpec(MockLLMElementSpec):
    config_schema = OverlayMockConfig


def library_elements() -> ElementRegistry:
    elements = ElementRegistry()
    elements.register_spec_class(OverlayMockSpec)
    elements.register_spec_class(MockAgentNodeElementSpec)
    return elements


def external_blueprint(node_rid: str = "library-agent") -> BlueprintDraft:
    return BlueprintDraft(
        name="Stored blueprint",
        description="Stored resources retain their factories and caller overlays",
        nodes=[{"rid": f"$ref:{node_rid}"}],
        plan=[{"uid": "respond", "node": f"$ref:{node_rid}"}],
    )


def inline_blueprint(token: str = "EMPTY") -> BlueprintDraft:
    return BlueprintDraft(
        name="Authored blueprint",
        llms=[
            {
                "rid": "model",
                "name": "Mock model",
                "type": "mock",
                "config": {"type": "mock", "base_url": "http://unused.invalid", "api_key": token},
            }
        ],
        nodes=[
            {
                "rid": "agent",
                "name": "Agent",
                "type": "mock_agent_node",
                "config": {"type": "mock_agent_node", "llm": "model"},
            }
        ],
        plan=[{"uid": "respond", "node": "agent"}],
    )


def dependency_blueprint(profile: str = "thread") -> dict:
    """Plugin schemas deliberately have no internal type discriminator."""
    return {
        "name": "Registered dependency blueprint",
        "tools": [
            {"rid": "leaf", "name": "Leaf", "type": "platform_dependency", "config": {}},
            {
                "rid": "middle",
                "name": "Middle",
                "type": "platform_dependency",
                "config": {"dependency": "leaf", "value": "middle"},
            },
        ],
        "nodes": [
            {
                "rid": "echo",
                "name": "Echo",
                "type": "platform_echo",
                "config": {"dependency": "middle", "prefix": "plugin:"},
                "execution": {"profile": profile},
            }
        ],
        "plan": [{"uid": "respond", "node": "echo"}],
    }
