from pydantic import BaseModel, Extra


class BaseRetrieverConfig(BaseModel):
    """
    Common fields for any Retriever.
    Pure configuration schema - no UI metadata.

    Subclasses must set `type` Literal and can add specific fields.
    UI metadata is now handled by ElementSpec classes.
    """

    class Config:
        extra = Extra.forbid
        arbitrary_types_allowed = True
