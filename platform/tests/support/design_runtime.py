"""Shared application-only runtime ports backed by real review/check use cases."""

from unittest.mock import create_autospec

from lumora.programs.ports import ChildExecution
from lumora.services.identity.domain import Identity
from plugins.adlc.programs.design import (
    DesignWork,
)
from support.feature_design import DesignerConfig, designer
from support.review_children import ReviewChildren
from support.verification import VerificationClock


class DesignRuntime:
    execution_id = "root"

    def __init__(self, decisions):
        self.owner, self.clock = Identity.user("owner"), VerificationClock()
        self.review_children = ReviewChildren(
            self, self.owner, self.clock, decisions, "Add an error case"
        )
        self.reviews = self.review_children.service
        self.decisions = self.review_children.decisions
        self.work, self.opened = [], self.review_children.opened
        self.child = None

    async def start_child(self, name, inputs, *, key, environment_imports=None):
        if name == "reviewer":
            return self.review_children.start(inputs, key)
        self.work.append(DesignWork.model_validate(inputs))
        child = create_autospec(ChildExecution, instance=True)
        child.execution_id = f"design-{len(self.work)}"
        child.result.return_value = await designer(self, inputs, DesignerConfig())
        self.child = child
        return child

    async def invoke_element(self, bundle, inputs, *, key, execution=None):
        return await self.review_children.invoke(inputs, key=key, execution_id=self.execution_id)

    async def receive(self, name, *, timeout=None):
        return await self.review_children.receive(name, timeout=timeout)

    async def sleep(self, seconds):
        pass
