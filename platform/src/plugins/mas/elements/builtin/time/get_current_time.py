from zoneinfo import ZoneInfo

"""
Tool for getting current date and time.
"""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from flareward.elements.agents.constants import ToolNames
from flareward.elements.ports.tool import BaseTool


class GetCurrentTimeArgs(BaseModel):
    """Arguments for getting current time."""

    timezone_name: str = Field(
        default="UTC",
        description="Timezone name (e.g., 'UTC', 'US/Eastern', 'Europe/London'). Defaults to UTC.",
    )
    include_timestamp: bool = Field(
        default=True, description="Whether to include Unix timestamp in the response"
    )


class GetCurrentTimeTool(BaseTool):
    """Get current date and time information."""

    name = ToolNames.TIME_GET_CURRENT
    description = """Get the current date and time.
    
Essential for handling date/time-relative queries like "last week", "yesterday",
"2 hours ago", "next month", or any task requiring current date/time context.

Returns current date, time, day of week, and timezone info."""

    args_schema = GetCurrentTimeArgs

    def __init__(self):
        """Initialize time tool (no dependencies needed)."""
        pass

    async def run(self, **kwargs) -> dict[str, Any]:
        """Get current time and date information."""

        args = GetCurrentTimeArgs(**kwargs)

        # Get current time in UTC
        now_utc = datetime.now(UTC)

        # Try to convert to requested timezone
        try:
            if args.timezone_name != "UTC":
                tz = ZoneInfo(args.timezone_name)
                now_local = now_utc.astimezone(tz)
            else:
                now_local = now_utc
        except Exception:
            # Fallback to UTC if timezone is invalid
            now_local = now_utc
            args.timezone_name = "UTC"

        # Format the response
        result = {
            "datetime": now_local.strftime("%Y-%m-%d %H:%M:%S"),
            "date": now_local.strftime("%Y-%m-%d"),
            "time": now_local.strftime("%H:%M:%S"),
            "day_of_week": now_local.strftime("%A"),
            "iso_format": now_local.isoformat(),
            "timezone": args.timezone_name,
            "human_readable": (
                f"{now_local.strftime('%A, %B %d, %Y at %I:%M:%S %p')} {args.timezone_name}"
            ),
        }

        # Add timestamp if requested
        if args.include_timestamp:
            result["timestamp"] = int(now_local.timestamp())

        return result
