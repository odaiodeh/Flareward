"""Secret-free authoring metadata; discovery is neither consent nor a capability."""

from pydantic import BaseModel, Field, JsonValue

from mas.domain.models import Model


class WorkflowAccessDescriptor(Model):
    purpose: str = Field(pattern=r"^[a-z][a-z0-9_.-]*@[1-9][0-9]*$")
    name: str = Field(min_length=1)
    description: str
    request_schema: dict[str, JsonValue]

    @classmethod
    def from_models(
        cls,
        purpose: str,
        name: str,
        description: str,
        parameters: type[BaseModel],
        scope: dict[str, JsonValue],
    ) -> WorkflowAccessDescriptor:
        """Reuse issuer request constraints with the invocation's root omitted."""
        schema = parameters.model_json_schema()
        properties = schema["properties"]
        old_scope = properties["scope"]
        definitions = schema.pop("$defs", {})
        reference = old_scope.get("$ref", "")
        if reference.startswith("#/$defs/"):
            definitions.pop(reference.removeprefix("#/$defs/"), None)
        scope = {**scope}
        scope_definitions = scope.pop("$defs", {})
        if not isinstance(scope_definitions, dict):
            raise ValueError("Workflow scope definitions must be objects")
        schema["$defs"] = {**definitions, **scope_definitions}
        scope["title"] = "Permissions"
        properties["scope"] = scope
        schema["default"] = {"scope": {}}
        if "default" in properties["ttl_seconds"]:
            schema["default"]["ttl_seconds"] = properties["ttl_seconds"]["default"]
        return cls(purpose=purpose, name=name, description=description, request_schema=schema)
