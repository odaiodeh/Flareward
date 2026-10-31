from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ValidationSettings(BaseSettings):
    """Environment-driven settings for graph validation rules."""

    model_config = SettingsConfigDict(env_prefix="GRAPH_", case_sensitive=False)

    required_start_nodes: set[str] = Field(default_factory=lambda: {"user_question_node"})
    required_end_nodes: set[str] = Field(default_factory=lambda: {"final_answer_node"})
    required_any_nodes: set[str] = Field(default_factory=set)

    # Maximum node constraints (None = unlimited)
    max_start_nodes: int | None = Field(default=1)
    max_end_nodes: int | None = Field(default=1)
    max_any_nodes: int | None = Field(default=30)
