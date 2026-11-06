"""Configuration admits only durable verification and known evidence authorities."""

import pytest
from cryptography.fernet import Fernet
from inbound.http_api.verification_auth import VerifierAuthenticator
from mas.application.verification.program_checks import ProgramCheckConfiguration
from mas.core.identity import Identity
from mas.domain.programs.models import ProgramRef
from mas_plugins.ci.github_config import GitHubCheckConfiguration
from pydantic import SecretStr, ValidationError
from runengine.adapters.coordination.config import LocalHostConfig
from support.check_runs import check_policy, source_policy
from support.github_checks import github_configuration
from support.verification import verification_authority, verification_policy

from config.platform_settings import PlatformSettings, VerificationAuthorityConfig


def settings(**values):
    return PlatformSettings(
        host=LocalHostConfig(),
        storage="mongo",
        authentication="session",
        secret_key=SecretStr("settings-fixture"),
        **values,
    )


def test_recoverable_issuance_requires_explicit_workflow_services_and_encryption():
    with pytest.raises(ValidationError, match="Mongo workflow access"):
        settings(recoverable_credential_issuance=True)
    with pytest.raises(ValidationError, match="encryption key"):
        settings(recoverable_credential_issuance=True, reviews_enabled=True)
    with pytest.raises(ValidationError, match="valid encryption key"):
        settings(
            recoverable_credential_issuance=True,
            reviews_enabled=True,
            credential_encryption_key=SecretStr("invalid"),
        )
    configured = settings(
        recoverable_credential_issuance=True,
        reviews_enabled=True,
        credential_encryption_key=SecretStr(Fernet.generate_key().decode()),
    )
    assert configured.recoverable_credential_issuance


def test_managed_delivery_requires_recoverable_issuance(tmp_path):
    with pytest.raises(ValidationError, match="recoverable credential issuance"):
        settings(workflow_credential_directory=tmp_path / "managed")
    configured = settings(
        workflow_credential_directory=tmp_path / "managed",
        recoverable_credential_issuance=True,
        reviews_enabled=True,
        credential_encryption_key=SecretStr(Fernet.generate_key().decode()),
    )
    assert configured.workflow_credential_directory == tmp_path / "managed"


def test_verification_is_explicit_and_requires_configured_verifiers():
    owner = Identity.user("owner")
    with pytest.raises(ValidationError, match="require verification services"):
        settings(verification_policies={"release@1": verification_policy(owner)})
    with pytest.raises(ValidationError, match="configured verifier"):
        settings(
            verification_enabled=True,
            verification_policies={"release@1": verification_policy(owner)},
        )
    authorities = {
        name: VerificationAuthorityConfig(credential_sha256=digest * 64, owners=(owner,))
        for name, digest in (("ci", "a"), ("scanner", "b"))
    }
    configured = settings(
        verification_enabled=True,
        verification_policies={"release@1": verification_policy(owner)},
        verification_authorities=authorities,
    )
    assert configured.verification_enabled


def test_volatile_application_records_cannot_back_durable_verification():
    with pytest.raises(ValidationError, match="durable Mongo"):
        PlatformSettings(
            host=LocalHostConfig(),
            storage="memory",
            authentication="session",
            secret_key=SecretStr("settings-fixture"),
            verification_enabled=True,
        )


def test_shared_credentials_cannot_impersonate_distinct_verifier_identities():
    owner = Identity.user("owner")
    with pytest.raises(ValueError, match="distinct"):
        VerifierAuthenticator(
            {name: ("a" * 64, verification_authority(owner, name)) for name in ("ci", "scanner")}
        )


def test_internal_check_verifiers_cannot_also_accept_external_attestations():
    owner = Identity.user("owner")
    configured = settings(
        verification_enabled=True,
        verification_policies={"source@1": source_policy(owner)},
        github_checks={"github@1": github_configuration(owner)},
    )
    assert configured.github_checks["github@1"].policy.verifier == "github-ci"
    with pytest.raises(ValidationError, match="either internal dispatch or external"):
        settings(
            verification_enabled=True,
            verification_policies={"source@1": source_policy(owner)},
            github_checks=configured.github_checks,
            verification_authorities={
                "github-ci": VerificationAuthorityConfig(
                    credential_sha256="a" * 64, owners=(owner,)
                )
            },
        )


def test_program_check_bindings_require_storage_and_exclusive_authority(tmp_path):
    owner = Identity.user("owner")
    binding = ProgramCheckConfiguration(
        policy=check_policy(owner),
        program_owner=Identity.user("trusted-verifier"),
        program=ProgramRef(program_id="checks", revision=1),
        content_digest="a" * 64,
    )
    configured = {
        "verification_enabled": True,
        "verification_policies": {"source@1": source_policy(owner, requires_reports=True)},
        "program_checks": {"program@1": binding},
        "artifact_directory": tmp_path / "artifacts",
    }
    assert settings(**configured).program_checks["program@1"] == binding
    with pytest.raises(ValidationError, match="require verification services"):
        settings(**{**configured, "verification_enabled": False})
    with pytest.raises(ValidationError, match="durable artifact storage"):
        settings(**{**configured, "artifact_directory": None})
    with pytest.raises(ValidationError, match="either internal dispatch or external"):
        settings(
            **configured,
            verification_authorities={
                binding.policy.verifier: VerificationAuthorityConfig(
                    credential_sha256="a" * 64, owners=(owner,)
                )
            },
        )
    with pytest.raises(ValidationError, match="unique across installed adapters"):
        settings(**configured, github_checks={"program@1": github_configuration(owner)})


def test_check_runner_binding_requires_a_matching_policy():
    owner = Identity.user("owner")
    config = github_configuration(owner)
    wrong = config.model_copy(
        update={"policy": config.policy.model_copy(update={"check": "other@1"})}
    )
    with pytest.raises(ValidationError, match="compatible verification policy"):
        settings(
            verification_enabled=True,
            verification_policies={"source@1": source_policy(owner)},
            github_checks={"github@1": wrong},
        )


def test_required_report_policy_cannot_use_a_status_only_runner():
    owner = Identity.user("owner")
    with pytest.raises(ValidationError, match="required reports"):
        settings(
            verification_enabled=True,
            verification_policies={"source@1": source_policy(owner, requires_reports=True)},
            github_checks={"github@1": github_configuration(owner)},
        )


def test_report_bindings_require_storage_and_explicit_private_download_policy(tmp_path):
    owner = Identity.user("owner")
    config = github_configuration(owner, reports=True)
    with pytest.raises(ValidationError, match="durable artifact storage"):
        settings(
            verification_enabled=True,
            verification_policies={"source@1": source_policy(owner)},
            github_checks={"github@1": config},
        )
    invalid = config.model_dump(mode="python")
    invalid.update(token="private-unparsed-provider-key", archive_hosts=frozenset())
    with pytest.raises(ValidationError, match="explicit archive") as error:
        settings(
            verification_enabled=True,
            verification_policies={"source@1": source_policy(owner)},
            github_checks={"github@1": invalid},
            artifact_directory=tmp_path,
        )
    assert "private-unparsed-provider-key" not in str(error.value)
    rotated = GitHubCheckConfiguration.model_validate(
        {**config.model_dump(mode="python"), "token": "rotated-private-test-token"}
    )
    assert rotated.digest == config.digest
