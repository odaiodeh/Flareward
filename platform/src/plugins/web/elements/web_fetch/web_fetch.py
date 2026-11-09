import logging
from typing import Any

import safehttpx
from html_to_markdown import convert

from flareward.elements.ports.tool import BaseTool
from plugins.web.elements.web_fetch.models import WebFetchArgs, WebFetchResponse

logger = logging.getLogger(__name__)


class WebFetchTool(BaseTool):
    name: str = "web_fetch"
    description: str = "Fetch a web page and return its content as markdown."
    args_schema = WebFetchArgs

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        args = WebFetchArgs(**kwargs)
        url = str(args.url)

        try:
            response = await safehttpx.get(url, _transport=False)
        except Exception as exc:
            logger.error(
                "tool.failed", extra={"tool_name": self.name, "url": url, "error": str(exc)}
            )
            return WebFetchResponse(success=False, url=url, error=str(exc)).model_dump()

        result = convert(response.text)
        content = result if isinstance(result, str) else result.content
        return WebFetchResponse(success=True, url=url, content=content).model_dump()
