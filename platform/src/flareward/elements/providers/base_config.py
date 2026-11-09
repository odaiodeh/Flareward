from pydantic import BaseModel, Extra


class ProviderBaseConfig(BaseModel):
    """
    Common fields for any provider implementation.
    Pure configuration schema - no UI metadata.

    UI metadata is now handled by ElementSpec classes.
    """

    class Config:
        extra = Extra.forbid
        arbitrary_types_allowed = True
