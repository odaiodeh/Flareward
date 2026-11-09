"""The existing public catalog/program APIs expose and execute typed operations."""

import httpx
import pytest
from support.http_programs import execute_program, publish_program
from support.operations import TextInput, TextResult, TextSpec, operation_graph

from flareward.api.app import create_app
from flareward.elements.catalog.service import CatalogService
from flareward.programs.domain.models import ProgramDefinition


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_catalog_to_publication_to_execution_uses_shared_operation_contracts(
    platform, application, profile
):
    async def authenticate(request):
        return platform.owner

    app = create_app(
        platform.programs,
        platform.executions,
        authenticate,
        catalog=CatalogService(application.elements),
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://platform"
    ) as http:
        detail = await http.get(f"/api/catalog/elements/operations/{TextSpec.type_key}")
        assert detail.status_code == 200, detail.text
        assert detail.json()["input_schema"] == TextInput.model_json_schema()
        assert detail.json()["output_schema"] == TextResult.model_json_schema()
        definition = ProgramDefinition(
            program_id="typed-api",
            name="Typed API",
            owner=platform.owner,
            implementation=operation_graph(profile),
        )
        reference = await publish_program(http, definition)
        result = await execute_program(http, reference, "typed-api-run", {"name": "http"})
        assert result["phase"] == "completed", result
        assert result["result"] == {"answer": "typed:middle:http"}
