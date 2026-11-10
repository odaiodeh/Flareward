"""Agent output parsing system."""

from lumora.elements.agents.parsers.base import (
    BaseOutputParser,
    OutputParser,
    ParseError,
    ParseErrorType,
    ParserConfig,
)
from lumora.elements.agents.parsers.json_parser import JsonParser, JsonParserConfig
from lumora.elements.agents.parsers.registry import ParserFactory, ParserRegistry
from lumora.elements.agents.parsers.text_parser import TextParser, TextParserConfig
from lumora.elements.agents.parsers.tool_call_parser import ToolCallParser

# Register default parsers with metadata
ParserRegistry.register(
    "tool_call",
    ToolCallParser,
    description="Parses ChatMessage.tool_calls format (default)",
    supported_formats=["tool_calls", "function_calls"],
    priority=90,
)

ParserRegistry.register(
    "text",
    TextParser,
    config_class=TextParserConfig,
    description="Parses structured text formats (ReAct, etc.)",
    supported_formats=["react", "text", "structured"],
    priority=70,
)

ParserRegistry.register(
    "json",
    JsonParser,
    config_class=JsonParserConfig,
    description="Parses JSON-formatted responses",
    supported_formats=["json", "openai_functions"],
    priority=80,
)

__all__ = [
    # Base classes
    "BaseOutputParser",
    "OutputParser",
    "ParseError",
    "ParseErrorType",
    "ParserConfig",
    # Parser implementations
    "ToolCallParser",
    "TextParser",
    "TextParserConfig",
    "JsonParser",
    "JsonParserConfig",
    # Registry system
    "ParserRegistry",
    "ParserFactory",
]
