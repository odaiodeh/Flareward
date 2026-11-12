"""File candidates keep storage authority outside coding and bind publication to bytes."""

import asyncio
from unittest.mock import create_autospec

import pytest
from pydantic import ValidationError
from support.artifacts import inline_content
from support.operations import operation_bundle
from support.verification import VerificationClock

from lumora.executions.domain.preferences import ExecutionSelection
from lumora.programs.ports import ProgramRuntime
from lumora.services.artifacts.domain.models import BlobArtifactRef
from lumora.services.verification.domain.models import (
    CheckEvidence,
    CheckReport,
    CheckReportSource,
    CheckVerdict,
    VerificationOutcome,
    VerificationSubject,
)
from lumora.services.workspaces.domain.files import InlineFile
from plugins.adlc.programs.coding import (
    COORDINATORS,
    CodingFileCandidate,
    CodingFileCandidateConfig,
    CodingFileWork,
    coding_file_candidate,
)
from plugins.adlc.programs.program import EngineeringFeedback


@pytest.fixture
def candidate(application):
    runtime = create_autospec(ProgramRuntime, instance=True)
    config = CodingFileCandidateConfig(
        coding=operation_bundle(application.elements),
        loader=operation_bundle(application.elements),
        reader=operation_bundle(application.elements),
        publisher=operation_bundle(application.elements),
        path="src/answer.py",
        execution=ExecutionSelection(profile="coding"),
        artifact_execution=ExecutionSelection(profile="storage"),
    )
    exported = InlineFile(path=config.path, content=inline_content(b"verified candidate"))
    reference = BlobArtifactRef(artifact_id="a" * 64, **exported.content.identity.model_dump())
    runtime.invoke_element.side_effect = [
        {"workspace": "root/isolated/work", "content": "I succeeded"},
        exported.model_dump(mode="json"),
        {"artifact": reference.model_dump(mode="json")},
    ]
    return CodingFileCandidate(runtime, config), runtime, config, reference, exported


async def test_repair_loads_exact_inputs_outside_coding_and_publishes_exact_export(candidate):
    service, runtime, config, reference, exported = candidate
    old = inline_content(b"previous candidate")
    report_bytes = inline_content(b"failed check report")
    previous = VerificationSubject(
        kind="blob-artifact@1",
        identity={"artifact_id": "c" * 64, **old.identity.model_dump()},
    )
    report = CheckReport(
        source=CheckReportSource(
            external_id="check:report", name="tests.txt", identity=report_bytes.identity
        ),
        content=BlobArtifactRef(artifact_id="f" * 64, **report_bytes.identity.model_dump()),
    )
    evidence = CheckEvidence(
        check="tests@1",
        verifier="ci",
        subject_fingerprint=previous.fingerprint,
        run_id="first-check",
        verdict=CheckVerdict.FAILED,
        recorded_at=VerificationClock()(),
        reports=(report,),
    )
    runtime.invoke_element.side_effect = [
        old.model_dump(mode="json"),
        report_bytes.model_dump(mode="json"),
        {"workspace": "root/isolated/work", "content": "I succeeded"},
        exported.model_dump(mode="json"),
        {"artifact": reference.model_dump(mode="json")},
    ]
    work = CodingFileWork(
        task={"prompt": "Implement addition", "context": "Keep the interface"},
        attempt=1,
        feedback=EngineeringFeedback(
            candidate=previous, verification=VerificationOutcome.REJECTED, evidence=(evidence,)
        ),
    )
    result = await service.run(work)
    assert result.subject.identity == reference.model_dump(mode="json")
    first, second, coded, read, published = runtime.invoke_element.await_args_list
    assert first.args == (config.loader, previous.identity)
    assert second.args == (config.loader, report.content.model_dump(mode="json"))
    assert all(
        call.kwargs["execution"] == config.artifact_execution for call in (first, second, published)
    )
    assert all(call.kwargs["execution"] == config.execution for call in (coded, read))
    assert "Keep the interface" in coded.args[1]["context"]
    assert coded.args[1]["files"] == [
        InlineFile(path=config.path, content=old).model_dump(mode="json"),
        InlineFile(
            path=".lumora/reports/" + report.content.artifact_id, content=report_bytes
        ).model_dump(mode="json"),
    ]
    assert all("artifact" not in file for file in coded.args[1]["files"])
    assert read.args == (config.reader, {"workspace": "root/isolated/work", "path": config.path})
    assert published.args == (config.publisher, exported.model_dump(mode="json"))


@pytest.mark.parametrize("failure", [RuntimeError("coding failed"), asyncio.CancelledError()])
async def test_failed_or_cancelled_coding_never_publishes_a_candidate(candidate, failure):
    service, runtime, _, _, _ = candidate
    runtime.invoke_element.side_effect = failure
    with pytest.raises(type(failure)):
        await service.run(CodingFileWork(task={"prompt": "Implement"}, attempt=0))
    assert runtime.invoke_element.await_count == 1


@pytest.mark.parametrize("effect", ["coding", "reading", "publication"])
async def test_incomplete_effect_results_cannot_become_candidates(candidate, effect):
    service, runtime, _, _, exported = candidate
    responses = [
        {"workspace": "root/work", "content": "done"},
        exported.model_dump(mode="json"),
        {"artifact": {"sha256": "b" * 64}},
    ]
    index = ("coding", "reading", "publication").index(effect)
    responses[index] = {}
    runtime.invoke_element.side_effect = responses
    with pytest.raises(ValueError, match="violates its contract"):
        await service.run(CodingFileWork(task={"prompt": "Implement"}, attempt=0))
    assert runtime.invoke_element.await_count == index + 1


@pytest.mark.parametrize("substitution", ["path", "content"])
async def test_exported_or_published_substitution_is_not_a_candidate(candidate, substitution):
    service, runtime, _, reference, exported = candidate
    responses = [
        {"workspace": "root/work", "content": "done"},
        exported.model_dump(mode="json"),
        {"artifact": reference.model_dump(mode="json")},
    ]
    if substitution == "path":
        responses[1]["path"] = "other.py"
    else:
        responses[2]["artifact"]["sha256"] = "b" * 64
    runtime.invoke_element.side_effect = responses
    with pytest.raises(ValueError, match="does not match"):
        await service.run(CodingFileWork(task={"prompt": "Implement"}, attempt=0))


async def test_changed_loaded_content_fails_before_coding(candidate):
    service, runtime, _, _, _ = candidate
    artifact = BlobArtifactRef(artifact_id="a" * 64, sha256="b" * 64, size_bytes=1)
    runtime.invoke_element.side_effect = [inline_content().model_dump(mode="json")]
    with pytest.raises(ValueError, match="does not match"):
        await service.run(
            CodingFileWork(
                task={
                    "prompt": "Implement",
                    "files": [{"artifact": artifact.model_dump(), "path": "input"}],
                },
                attempt=0,
            )
        )
    assert runtime.invoke_element.await_count == 1


async def test_invalid_task_is_refused_before_coding(candidate):
    _, runtime, config, _, _ = candidate
    with pytest.raises(ValueError, match="violates its contract"):
        await coding_file_candidate(
            runtime, {"task": {"description": "private input"}, "attempt": 0}, config
        )
    runtime.invoke_element.assert_not_awaited()


def test_registered_input_exposes_coding_fields_for_schema_driven_authoring():
    model = COORDINATORS[0].input_model
    assert model is CodingFileWork
    schema = model.model_json_schema()
    assert schema["properties"]["task"]["$ref"] == "#/$defs/CodingInput"
    assert schema["$defs"]["CodingInput"]["required"] == ["prompt"]


@pytest.mark.parametrize("path", ["../outside", "/absolute", "a\\b", "."])
def test_candidate_path_is_contained_before_execution(candidate, path):
    _, _, config, _, _ = candidate
    with pytest.raises(ValidationError):
        CodingFileCandidateConfig.model_validate({**config.model_dump(), "path": path})
