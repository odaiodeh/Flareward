from abc import ABC
from typing import Any, ClassVar

from pydantic import BaseModel

from mas.application.elements.cards.default import DefaultCardBuilder
from mas.application.elements.cards.interface import CardBuilder
from mas.application.elements.factory import BaseFactory
from mas.application.elements.validation import ElementValidator
from mas.core.enums import ResourceCategory


class BaseElementSpec(ABC):
    """
    Static compile‑time contract for every element spec.
    Subclasses must fill in all *required* ClassVars; optional ones
    can be omitted or overwritten.
    """

    # ── required metadata ────────────────────────────────────────────────
    category: ClassVar[ResourceCategory]
    type_key: ClassVar[str]
    name: ClassVar[str]
    description: ClassVar[str]
    config_schema: ClassVar[type[BaseModel]]
    input_schema: ClassVar[type[BaseModel] | None] = None
    result_schema: ClassVar[type[BaseModel] | None] = None
    factory_cls: ClassVar[type[BaseFactory[Any, Any]]]
    dependencies: ClassVar[list[ResourceCategory]] = []
    # ── optional metadata ------------------------------------------------
    is_abstract: ClassVar[bool] = True
    version: ClassVar[str] = "1.0.0"
    tags: ClassVar[list[str]] = []
    hints: ClassVar[list[Any]] = []
    hidden: ClassVar[bool] = False

    # ── optional validator ------------------------------------------------
    validator_cls: ClassVar[type[ElementValidator] | None] = None
    # ── card building ────────────────────────────────────────────────────
    capability_names: ClassVar[list[str]] = []
    card_builder_cls: ClassVar[type[CardBuilder]] = DefaultCardBuilder

    # ─────────────────────────────────────────────────────────────────────
    # compile‑time validation
    # ─────────────────────────────────────────────────────────────────────
    def __init_subclass__(cls, *, abstract: bool = False, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls.is_abstract = abstract
        if not abstract:
            cls.validate_declaration()

    @classmethod
    def validate_declaration(cls) -> None:
        """Only complete, concrete specifications can enter an installed catalog."""
        if cls.is_abstract:
            raise TypeError("Abstract element specifications cannot be registered")
        missing = [
            name for name in cls._collect_required_attrs() if getattr(cls, name, None) is None
        ]
        if missing:
            raise TypeError(f"{cls.__name__} is missing required spec attributes: {missing}")

    # ─────────────────────────────────────────────────────────────────────
    # helper lives *inside* the class
    # ─────────────────────────────────────────────────────────────────────
    @staticmethod
    def _collect_required_attrs() -> set[str]:
        """Base-contract fields with no default are required on installed specifications."""
        return {
            name for name in BaseElementSpec.__annotations__ if name not in BaseElementSpec.__dict__
        }

    # ─────────────────────────────────────────────────────────────────────
    # nice repr for debugging
    # ─────────────────────────────────────────────────────────────────────
    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"{self.__class__.__name__}(category={self.category.name}, type_key='{self.type_key}')"
        )
