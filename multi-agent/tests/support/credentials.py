"""Native async credential consumer uses the existing builder's deferred auth binding."""

import json

from mas.application.elements.factory import BaseFactory
from mas.application.elements.specification import BaseElementSpec
from mas.core.auth.credentials.credential import AuthCredential
from mas.core.element_deps import ElementBuildContext
from mas.core.enums import ResourceCategory
from mas.graph.state.graph_state import GraphState
from pydantic import BaseModel, ConfigDict


class CredentialConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    server_identifier: str = "test-issuer"
    scheme_type: str = "api_key"


class CredentialNode:
    def __init__(self, credential: AuthCredential, deps: ElementBuildContext) -> None:
        self._credential, self._deps = credential, deps

    async def __call__(self, state: GraphState, config) -> GraphState:
        headers = await self._credential.get_headers()
        context = self._deps.execution_ctx.context
        return GraphState.model_validate(
            {
                **state.serialize(),
                "output": json.dumps(
                    {"headers": headers, "context": context.model_dump(mode="json")}
                ),
            }
        )


class CredentialFactory(BaseFactory):
    def accepts(self, cfg: CredentialConfig, element_type: str) -> bool:
        return element_type == "platform_credential"

    def create(self, cfg: CredentialConfig, **dependencies) -> CredentialNode:
        return CredentialNode(dependencies["auth_credential"], dependencies["deps"])


class CredentialSpec(BaseElementSpec):
    category = ResourceCategory.NODE
    type_key = "platform_credential"
    name = "Credential fixture"
    description = "Read real receiver credentials through the application credential contract"
    config_schema = CredentialConfig
    factory_cls = CredentialFactory
    reads = set()
    writes = {"output"}
