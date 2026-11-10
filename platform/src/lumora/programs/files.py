"""Load bounded Program file inputs on explicitly selected artifact placement."""

from pydantic import ValidationError

from lumora.executions.domain.preferences import ExecutionSelection
from lumora.programs.ports import ElementCalls
from lumora.resources.domain.bundles import ElementBundle
from lumora.services.artifacts.domain.models import InlineContent
from lumora.services.workspaces.domain.files import ArtifactFile, InlineFile, InputFile


class ProgramFileInputs:
    def __init__(
        self, runtime: ElementCalls, loader: ElementBundle, execution: ExecutionSelection
    ) -> None:
        self._runtime, self._loader, self._execution = runtime, loader, execution

    async def prepare(self, files: tuple[InputFile, ...]) -> tuple[InlineFile, ...]:
        size = sum(
            file.artifact.size_bytes
            if isinstance(file, ArtifactFile)
            else file.content.identity.size_bytes
            for file in files
        )
        if size > 1_048_576:
            raise ValueError("Program file inputs exceed their inline transfer limit")
        prepared = []
        for index, file in enumerate(files):
            if isinstance(file, InlineFile):
                prepared.append(file)
                continue
            value = await self._runtime.invoke_element(
                self._loader,
                file.artifact.model_dump(mode="json"),
                key=f"load-{index}",
                execution=self._execution,
            )
            try:
                content = InlineContent.model_validate(value)
            except ValidationError:
                raise ValueError("Loaded file content violates its contract") from None
            if (
                content.identity.sha256 != file.artifact.sha256
                or content.identity.size_bytes != file.artifact.size_bytes
            ):
                raise ValueError("Loaded file content does not match the requested artifact")
            prepared.append(InlineFile(path=file.path, content=content))
        return tuple(prepared)
