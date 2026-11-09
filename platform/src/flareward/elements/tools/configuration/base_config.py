from pydantic import BaseModel, Extra


class BaseToolConfig(BaseModel):
    """
    Common fields for any tool.
    Pure configuration schema - no UI metadata.

    Subclasses must define a Literal `type` field and can add specific fields.
    UI metadata is now handled by ElementSpec classes.
    """

    class Config:
        extra = Extra.forbid
        arbitrary_types_allowed = True
