"""Actual private consent storage preserves audit and fences expiry using Mongo's clock."""

from datetime import UTC, datetime, timedelta

import pytest
from mas.core.identity import Identity
from mas.domain.execution.access import WorkflowAccess
from mas.domain.execution.consent import WorkflowConsent
from outbound.mongo.workflow_consents import MongoWorkflowConsents
from support.workflow_consents import assert_consent_store_contract


async def test_mongo_consent_contract_and_server_clock_expiry(mongo_database):
    store = MongoWorkflowConsents(mongo_database)
    now = datetime.now(UTC)
    consent = WorkflowConsent(
        consent_id="a" * 32,
        source_id="scheduled-source",
        owner=Identity.user("owner"),
        approved_by=Identity.user("owner"),
        approved_at=now,
        expires_at=now + timedelta(hours=1),
        definition_sha256="a" * 64,
        prepared_sha256="b" * 64,
        requirements=(
            WorkflowAccess(
                purpose="review@1", scope={"actions": ["read"], "policies": ["release@1"]}
            ),
        ),
    )
    await assert_consent_store_contract(store, consent)
    expired = consent.model_copy(
        update={
            "consent_id": "b" * 32,
            "approved_at": now - timedelta(hours=2),
            "expires_at": now - timedelta(hours=1),
        }
    )
    await store.create(expired)
    with pytest.raises(PermissionError):
        # A slow worker clock cannot authorize an already expired consent.
        await store.get(expired.consent_id, expired.owner, active_at=now - timedelta(hours=2))
    row = await mongo_database.workflow_consents.find_one({"_id": consent.consent_id})
    assert row["revoked"] and row["data"] == consent.model_dump_json()
