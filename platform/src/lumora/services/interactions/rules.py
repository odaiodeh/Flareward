"""Validated rule commands apply immutable policy without knowing its persistence."""

from dataclasses import replace
from enum import StrEnum

from pydantic import Field

from lumora.models import Model
from lumora.services.interactions.tools.models import ApprovalOverrides, ApprovalRuleSet


class ApprovalRuleAction(StrEnum):
    APPROVE = "auto_approve"
    REJECT = "auto_reject"
    CLEAR = "clear"


class ApprovalRuleChange(Model):
    action: ApprovalRuleAction
    node_uid: str | None = Field(default=None, min_length=1)
    tool_name: str | None = Field(default=None, min_length=1)

    def apply(self, previous: ApprovalOverrides) -> ApprovalOverrides:
        if self.action == ApprovalRuleAction.CLEAR and self.tool_name is None:
            if self.node_uid is None:
                return ApprovalOverrides()
            return replace(
                previous,
                node_rules={
                    uid: rules for uid, rules in previous.node_rules.items() if uid != self.node_uid
                },
            )
        if (
            self.action == ApprovalRuleAction.CLEAR
            and self.node_uid is not None
            and self.node_uid not in previous.node_rules
        ):
            return previous
        rules = (
            previous.global_rules
            if self.node_uid is None
            else previous.node_rules.get(self.node_uid, ApprovalRuleSet())
        )
        if self.tool_name is None:
            rules = replace(
                rules,
                approve_all=self.action == ApprovalRuleAction.APPROVE,
                reject_all=self.action == ApprovalRuleAction.REJECT,
            )
        else:
            approve = rules.auto_approve_tools - {self.tool_name}
            reject = rules.auto_reject_tools - {self.tool_name}
            rules = replace(
                rules,
                auto_approve_tools=approve
                | ({self.tool_name} if self.action == ApprovalRuleAction.APPROVE else set()),
                auto_reject_tools=reject
                | ({self.tool_name} if self.action == ApprovalRuleAction.REJECT else set()),
            )
        if self.node_uid is None:
            return replace(previous, global_rules=rules)
        return replace(previous, node_rules={**previous.node_rules, self.node_uid: rules})
