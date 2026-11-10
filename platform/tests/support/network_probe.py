"""Installed deterministic element checks actual receiver HTTP access."""

import json

import httpx
from pydantic import AnyHttpUrl, BaseModel, ConfigDict

from lumora.elements.factory import BaseFactory
from lumora.elements.node import BaseNode
from lumora.programs.graph.state.state_view import StateView
from lumora.programs.graph_elements import GraphElementSpec
from lumora.resources.domain.categories import ResourceCategory


class NetworkProbeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    urls: tuple[AnyHttpUrl, ...]


class NetworkProbeNode(BaseNode):
    WRITES = {"output"}

    def __init__(self, urls: tuple[AnyHttpUrl, ...]) -> None:
        super().__init__()
        self._urls = urls

    async def run(self, state: StateView) -> StateView:
        results = []
        async with httpx.AsyncClient(timeout=5) as client:
            for url in self._urls:
                try:
                    response = await client.get(str(url))
                    response.raise_for_status()
                except httpx.HTTPError as error:
                    results.append({"allowed": False, "error": type(error).__name__})
                else:
                    results.append({"allowed": True, "body": response.text})
        state["output"] = json.dumps(results)
        return state


class NetworkProbeFactory(BaseFactory):
    def accepts(self, cfg: NetworkProbeConfig, element_type: str) -> bool:
        return element_type == "network_probe"

    def create(self, cfg: NetworkProbeConfig, **dependencies) -> NetworkProbeNode:
        return NetworkProbeNode(cfg.urls)


class NetworkProbeSpec(GraphElementSpec):
    category = ResourceCategory.NODE
    type_key = "network_probe"
    name = "Receiver network probe"
    description = "Verify a deployment policy against reachable HTTP services"
    config_schema = NetworkProbeConfig
    factory_cls = NetworkProbeFactory
    reads = NetworkProbeNode.total_reads()
    writes = NetworkProbeNode.total_writes()
