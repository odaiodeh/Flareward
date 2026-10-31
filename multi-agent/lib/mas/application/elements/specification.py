from abc import ABC
from typing import (
    Any,
    ClassVar,
    Union,
    get_args,
    get_origin,
)

from pydantic import BaseModel

from mas.application.elements.cards.default import DefaultCardBuilder
from mas.application.elements.cards.interface import CardBuilder
from mas.application.elements.factory import BaseFactory
from mas.application.elements.validation import ElementValidator
from mas.core.enums import ResourceCategory
from mas.graph.state.graph_state import Channel


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
    factory_cls: ClassVar[type[BaseFactory]]
    dependencies: ClassVar[list[ResourceCategory]] = []
    reads: ClassVar[set[Channel]] = set()
    writes: ClassVar[set[Channel]] = set()
    # ── optional metadata ------------------------------------------------
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
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)

        missing = [
            name for name in cls._collect_required_attrs() if getattr(cls, name, None) is None
        ]
        if missing:
            raise TypeError(f"{cls.__name__} is missing required spec attributes: {missing}")

    # ─────────────────────────────────────────────────────────────────────
    # helper lives *inside* the class
    # ─────────────────────────────────────────────────────────────────────
    @classmethod
    def _collect_required_attrs(cls) -> set[str]:
        """
        Return names of every attribute declared on *BaseElementSpec* that is
        required (i.e. no default value and not annotated as Optional[...]).

        We intentionally inspect `BaseElementSpec` (the contract) rather than
        `cls` (the concrete subclass) so the rule set is stable.
        """
        base = BaseElementSpec  # alias for readability
        required: set[str] = set()

        for name, anno in base.__annotations__.items():
            # Default provided → optional
            if name in base.__dict__:
                continue

            # Optional[...] or Union[..., None] → optional
            origin = get_origin(anno)
            if origin is Union and type(None) in get_args(anno):
                continue

            required.add(name)

        return required

    # ─────────────────────────────────────────────────────────────────────
    # nice repr for debugging
    # ─────────────────────────────────────────────────────────────────────
    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"{self.__class__.__name__}(category={self.category.name}, type_key='{self.type_key}')"
        )
