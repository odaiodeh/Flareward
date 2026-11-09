"""The memory adapter must satisfy the same persistence semantics as Mongo."""

import pytest
from support.program_store_contracts import PROGRAM_STORE_CONTRACTS

from flareward.programs.adapters.memory.program_repository import MemoryProgramRepository


@pytest.mark.parametrize("contract", PROGRAM_STORE_CONTRACTS)
async def test_memory_program_repository(contract):
    await contract(MemoryProgramRepository())
