"""Publish and pin a verifier through the normal owner-authorized Program API."""

from dataclasses import dataclass

import httpx

from lumora.programs.domain.models import ProgramDefinition, ProgramRevision
from lumora.services.verification.check_ports import CheckRunnerPolicy
from lumora.services.verification.program_checks import ProgramCheckConfiguration
from support.http_programs import publish_program


@dataclass(frozen=True)
class CheckProgramSetup:
    definition: ProgramDefinition
    policy: CheckRunnerPolicy
    input_artifact_max_bytes: int | None = None

    async def publish(
        self, http: httpx.AsyncClient, headers: dict[str, str]
    ) -> ProgramCheckConfiguration:
        reference = await publish_program(http, self.definition, headers=headers)
        response = await http.get(
            f"/api/programs/{reference.program_id}/revisions/{reference.revision}", headers=headers
        )
        assert response.status_code == 200, response.text
        revision = ProgramRevision.model_validate(response.json())
        return ProgramCheckConfiguration(
            policy=self.policy,
            program_owner=self.definition.owner,
            program=reference,
            content_digest=revision.content_digest,
            input_artifact_max_bytes=self.input_artifact_max_bytes,
        )
