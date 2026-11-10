"""Native ASGI server command, independent of the legacy Flask composition root."""

import asyncio
from importlib import import_module

import typer
import uvicorn
from runengine.adapters.coordination.config import LocalHostConfig

from lumora.bootstrap.settings.platform_settings import PlatformSettings
from lumora.bootstrap.settings.worker_settings import WorkerSettings

app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)


@app.callback()
def platform() -> None:
    """Lumora program platform commands."""


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", envvar="LUMORA_BIND_HOST"),
    port: int = typer.Option(13457, min=1, max=65535, envvar="LUMORA_BIND_PORT"),
    workers: int = typer.Option(1, min=1, envvar="LUMORA_HTTP_WORKERS"),
) -> None:
    """Serve FastAPI with lifespan-owned async services and execution observation."""
    settings = PlatformSettings()
    if workers > 1 and isinstance(settings.host, LocalHostConfig):
        raise typer.BadParameter("Local coordination requires one HTTP worker")
    uvicorn.run(
        "lumora.bootstrap.asgi:create_app",
        factory=True,
        host=host,
        port=port,
        workers=workers,
    )


def main() -> None:
    app()


@app.command()
def worker() -> None:
    """Serve installed programs with Run Engine's durable coordination worker."""
    run = import_module("lumora.bootstrap.worker").run_worker
    with asyncio.Runner() as runner:
        runner.run(run(WorkerSettings()))


if __name__ == "__main__":
    main()
