from abc import ABC, abstractmethod
from typing import Any


class BaseFactory[Cfg, Out](ABC):
    """
    Abstract interface for all plugin factories (LLMs, tools, nodes, retrievers, etc.).

    Defines a two‐step contract:
      1) accepts(cfg) → bool
           “Do I know how to build from this config?”
      2) create(cfg, **deps) → Out
           “Given a validated config and any injected dependencies,
            produce the plugin instance.”

    This lets PluginRegistry and NodeFactory remain agnostic to specific
    plugin types, while still enabling drop-in extensions via new factories.
    """

    @abstractmethod
    def accepts(self, cfg: Cfg, element_type: str) -> bool:
        """
        Return True if this factory can build an instance from the given config.

        GUIDELINES:
        1. PRIMARY: Use element_type for main factory selection (99% of cases)
        2. SECONDARY: Use cfg for advanced validation only when needed
        3. PERFORMANCE: Keep cfg inspection lightweight
        4. CLARITY: Document any cfg-based logic clearly

        :param cfg: Validated configuration object
        :param element_type: Primary element type identifier
        :return: True if this factory can handle this config
        """
        ...

    @abstractmethod
    def create(self, cfg: Cfg, **deps: Any) -> Out:
        """
        Instantiate and return the plugin from the given config.

        :param cfg: A validated configuration object.
        :param deps: Arbitrary keyword‐injected dependencies (e.g. llm, tools, retriever).
        :raises Exception: on invalid config or instantiation failure.
        :return: The created plugin instance.
        """
        ...
