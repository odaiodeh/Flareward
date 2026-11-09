"""Persist provider reports through the existing artifact service before attesting."""

import hashlib
import json
from collections.abc import AsyncGenerator
from contextlib import aclosing

from flareward.services.artifacts.access_models import ArtifactActor
from flareward.services.artifacts.domain.models import PublishArtifact
from flareward.services.artifacts.service import ArtifactService
from flareward.services.verification.check_ports import CheckReports
from flareward.services.verification.domain.check_runs import CheckRun
from flareward.services.verification.domain.models import CheckReport, CheckReportSource


class CheckReportCollector:
    def __init__(self, artifacts: ArtifactService) -> None:
        self._artifacts = artifacts

    async def collect(self, run: CheckRun, provider: CheckReports) -> tuple[CheckReport, ...]:
        if run.report_sources is None:
            raise ValueError("Check reports require an admitted source manifest")
        reports = []
        for source in run.report_sources:
            key = hashlib.sha256(
                json.dumps([run.intent_id, source.external_id], separators=(",", ":")).encode()
            ).hexdigest()
            # Lazy acquisition allows a committed publication to recover even after
            # the provider archive expires. The shared repository deduplicates it.
            async with aclosing(self._content(run, source, provider)) as content:
                record = await self._artifacts.publish(
                    PublishArtifact(
                        key=key,
                        namespace="verification-reports",
                        name=source.name,
                        media_type=source.media_type,
                        **source.identity.model_dump(),
                    ),
                    content,
                    ArtifactActor(run.plan.owner),
                )
            reports.append(CheckReport(source=source, content=record.reference))
        return tuple(reports)

    @staticmethod
    async def _content(
        run: CheckRun, source: CheckReportSource, provider: CheckReports
    ) -> AsyncGenerator[bytes]:
        async with provider.open(run, source) as content:
            async for chunk in content:
                yield chunk
