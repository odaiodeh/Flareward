"""
Time utilities for date/time operations.

Provides reusable helpers for UTC datetime formatting
used across services and repositories.
"""
from datetime import datetime


def format_utc_iso(dt: datetime) -> str:
    """
    Format a UTC datetime to ISO 8601 string with 'Z' suffix.

    Converts Python's '+00:00' UTC offset to the standard 'Z' suffix
    commonly used in JSON APIs and ISO 8601 interchange.

    Args:
        dt: A timezone-aware datetime in UTC

    Returns:
        ISO format string with 'Z' suffix (e.g., '2024-01-01T00:00:00Z')
    """
    return dt.isoformat().replace('+00:00', 'Z')
