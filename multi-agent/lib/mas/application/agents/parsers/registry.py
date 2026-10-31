"""Parser registry and factory system."""

import json
import logging
from dataclasses import dataclass
from enum import Enum

from mas.application.agents.parsers.base import (
    BaseOutputParser,
    ParseError,
    ParseErrorType,
    ParserConfig,
)
from mas.domain.agents import AgentAction, AgentFinish
from mas.domain.messages import ChatMessage

logger = logging.getLogger(__name__)


class ParserSelectionStrategy(Enum):
    """Strategies for auto-selecting parsers."""

    MESSAGE_ANALYSIS = "message_analysis"  # Analyze message content to choose parser
    MODEL_BASED = "model_based"  # Choose based on model capabilities
    FALLBACK_CHAIN = "fallback_chain"  # Try multiple parsers in order
    CONFIGURATION = "configuration"  # Use explicit configuration


@dataclass
class ParserRegistration:
    """Registration info for a parser."""

    name: str
    parser_class: type[BaseOutputParser]
    config_class: type[ParserConfig]
    description: str
    supported_formats: list[str]
    priority: int = 50  # Higher = preferred for auto-selection


class ParserRegistry:
    """Centralized registry for output parsers."""

    _parsers: dict[str, ParserRegistration] = {}

    @classmethod
    def register(
        cls,
        name: str,
        parser_class: type[BaseOutputParser],
        config_class: type[ParserConfig] | None = None,
        description: str = "",
        supported_formats: list[str] | None = None,
        priority: int = 50,
    ) -> None:
        """Register a parser in the registry."""
        if name in cls._parsers:
            logger.warning(f"Overriding existing parser registration: {name}")

        cls._parsers[name] = ParserRegistration(
            name=name,
            parser_class=parser_class,
            config_class=config_class or ParserConfig,
            description=description or f"{parser_class.__name__} parser",
            supported_formats=supported_formats or [],
            priority=priority,
        )

        logger.debug(f"Registered parser '{name}': {parser_class.__name__}")

    @classmethod
    def unregister(cls, name: str) -> bool:
        """Unregister a parser."""
        if name in cls._parsers:
            del cls._parsers[name]
            logger.debug(f"Unregistered parser: {name}")
            return True
        return False

    @classmethod
    def get_parser_class(cls, name: str) -> type[BaseOutputParser] | None:
        """Get parser class by name."""
        registration = cls._parsers.get(name)
        return registration.parser_class if registration else None

    @classmethod
    def get_config_class(cls, name: str) -> type[ParserConfig] | None:
        """Get config class for parser."""
        registration = cls._parsers.get(name)
        return registration.config_class if registration else None

    @classmethod
    def list_parsers(cls) -> list[str]:
        """Get list of registered parser names."""
        return list(cls._parsers.keys())

    @classmethod
    def get_parser_info(cls, name: str) -> ParserRegistration | None:
        """Get full registration info for parser."""
        return cls._parsers.get(name)

    @classmethod
    def get_parsers_by_format(cls, format_name: str) -> list[str]:
        """Get parsers that support a specific format."""
        matching = []
        for name, registration in cls._parsers.items():
            if format_name in registration.supported_formats:
                matching.append(name)

        # Sort by priority (highest first)
        matching.sort(key=lambda n: cls._parsers[n].priority, reverse=True)
        return matching

    @classmethod
    def get_parsers_by_priority(cls) -> list[str]:
        """Get all parsers sorted by priority."""
        parsers = list(cls._parsers.keys())
        parsers.sort(key=lambda n: cls._parsers[n].priority, reverse=True)
        return parsers


class ParserFactory:
    """Factory for creating parser instances."""

    @staticmethod
    def create(parser_name: str, config: ParserConfig | None = None, **kwargs) -> BaseOutputParser:
        """Create parser instance by name."""
        registration = ParserRegistry.get_parser_info(parser_name)
        if not registration:
            available = ParserRegistry.list_parsers()
            raise ValueError(f"Unknown parser: {parser_name}. Available: {available}")

        # Create config if not provided
        if config is None:
            config = registration.config_class(**kwargs)
        elif kwargs:
            # Merge kwargs into existing config
            config_dict = config.__dict__.copy()
            config_dict.update(kwargs)
            config = registration.config_class(**config_dict)

        try:
            return registration.parser_class(config)
        except Exception as e:
            raise TypeError(f"Failed to create parser '{parser_name}': {e}") from e

    @staticmethod
    def auto_select(
        message: ChatMessage | None = None,
        strategy: ParserSelectionStrategy = ParserSelectionStrategy.MESSAGE_ANALYSIS,
        fallback: str = "tool_call",
        **config_kwargs,
    ) -> BaseOutputParser:
        """Auto-select and create appropriate parser."""
        selected_parser = None

        try:
            if strategy == ParserSelectionStrategy.MESSAGE_ANALYSIS:
                selected_parser = ParserFactory._analyze_message_for_parser(message)
            elif strategy == ParserSelectionStrategy.MODEL_BASED:
                selected_parser = ParserFactory._select_by_model(message)
            elif strategy == ParserSelectionStrategy.FALLBACK_CHAIN:
                selected_parser = ParserFactory._select_by_fallback_chain(message)

            # Use fallback if no parser selected
            if not selected_parser:
                selected_parser = fallback

            logger.debug(f"Auto-selected parser: {selected_parser}")
            return ParserFactory.create(selected_parser, **config_kwargs)

        except Exception as e:
            logger.warning(f"Auto-selection failed: {e}. Using fallback: {fallback}")
            return ParserFactory.create(fallback, **config_kwargs)

    @staticmethod
    def _analyze_message_for_parser(message: ChatMessage | None) -> str | None:
        """Analyze message content to select appropriate parser."""
        if not message or not message.content:
            return None

        content = message.content.strip()

        # Check for tool calls first
        if hasattr(message, "tool_calls") and message.tool_calls:
            return "tool_call"

        # Check for JSON format
        if content.startswith("{") and content.endswith("}"):
            try:
                json.loads(content)
                return "json"
            except json.JSONDecodeError:
                pass

        # Check for structured text patterns
        if any(pattern in content.lower() for pattern in ["action:", "final answer:", "thought:"]):
            return "text"

        # Default to tool_call parser for assistant messages
        return "tool_call"

    @staticmethod
    def _select_by_model(message: ChatMessage | None) -> str | None:
        """Select parser based on model capabilities."""
        # This could be enhanced to check message metadata for model info
        # For now, use simple heuristics

        if not message:
            return None

        # If message has tool_calls, use tool_call parser
        if hasattr(message, "tool_calls") and message.tool_calls:
            return "tool_call"

        # Could add model-specific logic here
        # e.g., some models prefer JSON, others prefer text formats

        return None

    @staticmethod
    def _select_by_fallback_chain(message: ChatMessage | None) -> str | None:
        """Try parsers in priority order until one works."""
        if not message:
            return None

        # Get parsers by priority
        parsers = ParserRegistry.get_parsers_by_priority()

        for parser_name in parsers:
            try:
                # Try to create parser and do a quick validation
                parser = ParserFactory.create(parser_name)

                # Basic validation - can this parser handle the message?
                parser.validate_message(message)

                # If validation passes, use this parser
                return parser_name

            except Exception:
                # Try next parser
                continue

        return None

    @staticmethod
    def create_multi_parser(
        parser_names: list[str], configs: dict[str, ParserConfig] | None = None
    ) -> MultiParser:
        """Create a multi-parser that tries multiple parsers in order."""
        return MultiParser(parser_names, configs or {})


class MultiParser(BaseOutputParser):
    """Parser that tries multiple parsers in sequence."""

    def __init__(self, parser_names: list[str], configs: dict[str, ParserConfig] | None = None):
        """Initialize multi-parser."""
        super().__init__()
        self.parser_names = parser_names
        self.parsers = []

        # Create parser instances
        for name in parser_names:
            config = configs.get(name) if configs else None
            parser = ParserFactory.create(name, config)
            self.parsers.append((name, parser))

    def parse(self, message: ChatMessage) -> list[AgentAction] | AgentFinish:
        """Try parsers in sequence until one succeeds."""
        errors = []

        for name, parser in self.parsers:
            try:
                result = parser.parse(message)
                logger.debug(f"MultiParser: {name} succeeded")
                return result
            except Exception as e:
                logger.debug(f"MultiParser: {name} failed: {e}")
                errors.append(f"{name}: {e}")

        # All parsers failed
        raise ParseError(
            f"All parsers failed. Errors: {'; '.join(errors)}",
            ParseErrorType.UNKNOWN_FORMAT,
            message.content or "",
            recoverable=True,
            context={"parser_errors": errors, "parsers_tried": self.parser_names},
        )

    def parse_error_recovery(self, error) -> AgentAction:
        """Use first parser's error recovery."""
        if self.parsers:
            return self.parsers[0][1].parse_error_recovery(error)

        return super().parse_error_recovery(error)
