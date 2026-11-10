"""The development adapter obeys the same private claim/fencing contract as Mongo."""

from support.execution_claims import assert_submission_claim_contract

from lumora.executions.adapters.memory.execution_repository import MemoryExecutionRepository


async def test_memory_admission_claims_fence_stale_updates_and_preserve_cancel_intent():
    await assert_submission_claim_contract(MemoryExecutionRepository())
