"""Publish the shared feature composition through normal native Program endpoints."""

from dataclasses import dataclass

import httpx
from mas.application.elements.catalog.element_registry import ElementRegistry
from mas.core.identity import Identity
from mas.domain.execution.access import WorkflowAccess
from mas.domain.programs.models import (
    ApplicationDefinition,
    ProgramBody,
    ProgramDefinition,
    ProgramRef,
)
from mas_plugins.engineering.design import DesignResult, FeatureRequest
from mas_plugins.engineering.feature import CodingFeatureInput, CodingFeatureResult
from mas_plugins.engineering.program import EngineeringInput, EngineeringResult

from support.engineering_programs import engineering_configuration
from support.feature_design import design_definition
from support.http_programs import publish_program


@dataclass(frozen=True)
class FeaturePrograms:
    design: ProgramRef
    engineering: ProgramRef
    feature: ProgramRef


async def publish_feature(
    http: httpx.AsyncClient,
    human: dict[str, str],
    owner: Identity,
    registry: ElementRegistry,
    body: ProgramBody,
    profile: str,
    *,
    review_timeout_seconds: int = 60,
    runners: tuple[str, ...] = ("fixture@1",),
    max_check_polls: int = 20,
    check_poll_interval_seconds: float = 0.1,
) -> FeaturePrograms:
    design = await publish_program(
        http,
        ProgramDefinition(
            program_id="design",
            name="Design",
            owner=owner,
            implementation=design_definition(
                registry, profile, review_timeout_seconds=review_timeout_seconds
            ),
            input_schema=FeatureRequest.model_json_schema(),
            output_schema=DesignResult.model_json_schema(),
        ),
        headers=human,
    )
    config = engineering_configuration(
        registry,
        profile=profile,
        verification_policy="engineering@1",
        runners=runners,
        max_polls=max_check_polls,
        poll_interval_seconds=check_poll_interval_seconds,
        review_timeout_seconds=review_timeout_seconds,
    )
    engineering = await publish_program(
        http,
        ProgramDefinition(
            program_id="engineering",
            name="Engineering",
            owner=owner,
            implementation=ApplicationDefinition(
                implementation="engineering",
                version="1",
                config=config.model_dump(mode="json"),
                children={"implementation": body, "repair": body},
            ),
            input_schema=EngineeringInput.model_json_schema(),
            output_schema=EngineeringResult.model_json_schema(),
        ),
        headers=human,
    )
    feature = await publish_program(
        http,
        ProgramDefinition(
            program_id="feature",
            name="Feature",
            owner=owner,
            implementation=ApplicationDefinition(
                implementation="coding_feature",
                version="1",
                children={"design": design, "engineering": engineering},
            ),
            input_schema=CodingFeatureInput.model_json_schema(),
            output_schema=CodingFeatureResult.model_json_schema(),
        ),
        headers=human,
    )
    return FeaturePrograms(design, engineering, feature)


def feature_workflow_access(
    *, ttl_seconds: int = 60, renewable_for_seconds: int = 180
) -> tuple[WorkflowAccess, ...]:
    return tuple(
        WorkflowAccess(
            purpose=purpose,
            scope=scope,
            ttl_seconds=ttl_seconds,
            renewable_for_seconds=renewable_for_seconds,
        )
        for purpose, scope in (
            ("review@1", {"policies": ["release@1"], "actions": ["open", "read", "close"]}),
            (
                "verification@1",
                {"policies": ["engineering@1"], "actions": ["create", "read", "run_check"]},
            ),
            (
                "artifact@1",
                {
                    "namespaces": ["engineering", "verification-reports"],
                    "actions": ["read", "publish"],
                    "max_bytes": 65_536,
                },
            ),
        )
    )
