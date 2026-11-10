"""A deterministic business effect owns deduplication independently of infrastructure delivery."""

import asyncio
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from lumora.elements.factory import BaseFactory
from lumora.elements.node import BaseNode
from lumora.programs.graph.state.state_view import StateView
from lumora.programs.graph_elements import GraphElementSpec
from lumora.programs.ports import ProgramRuntime
from lumora.resources.domain.bundles import ElementBundle
from lumora.resources.domain.categories import ResourceCategory

__runengine_contract__ = "lumora-test-recovery-v1"


class EffectConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    database: str
    committed: str
    release: str
    operation_key: str


class EffectNode(BaseNode):
    READS = set()
    WRITES = {"output"}

    def __init__(self, config: EffectConfig) -> None:
        super().__init__()
        self._config = config

    async def run(self, state: StateView) -> StateView:
        cfg = self._config
        with closing(sqlite3.connect(cfg.database)) as connection, connection:
            connection.execute("CREATE TABLE IF NOT EXISTS effects (key TEXT PRIMARY KEY)")
            connection.execute("INSERT OR IGNORE INTO effects VALUES (?)", (cfg.operation_key,))
            connection.execute("CREATE TABLE IF NOT EXISTS deliveries (pid INTEGER)")
            connection.execute("INSERT INTO deliveries VALUES (?)", (os.getpid(),))
        Path(cfg.committed).touch()
        while not Path(cfg.release).exists():
            await asyncio.sleep(0.02)
        state["output"] = "committed"
        return state


class EffectFactory(BaseFactory):
    def accepts(self, cfg: EffectConfig, element_type: str) -> bool:
        return element_type == "platform_effect"

    def create(self, cfg: EffectConfig, **dependencies) -> EffectNode:
        return EffectNode(cfg)


class EffectSpec(GraphElementSpec):
    category = ResourceCategory.NODE
    type_key = "platform_effect"
    name = "Idempotent effect fixture"
    description = "Commit once while allowing infrastructure to redeliver a lost invocation"
    config_schema = EffectConfig
    factory_cls = EffectFactory
    reads = EffectNode.total_reads()
    writes = EffectNode.total_writes()


class RecoveryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bundle: ElementBundle


async def recovery_program(runtime: ProgramRuntime, inputs: dict, config: RecoveryConfig) -> dict:
    result = await runtime.invoke_element(config.bundle, {}, key="one-effect")
    return {"answer": result["output"]}


def effect_counts(database: Path) -> tuple[int, list[int]]:
    with closing(sqlite3.connect(database)) as connection:
        effects = connection.execute("SELECT COUNT(*) FROM effects").fetchone()[0]
        pids = [row[0] for row in connection.execute("SELECT pid FROM deliveries")]
        return effects, pids
