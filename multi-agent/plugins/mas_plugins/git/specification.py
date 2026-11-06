"""Git is an ordinary optional provider and operations plugin, not engine behavior."""

from typing import Any

from mas.application.elements.factory import BaseFactory
from mas.application.elements.specification import BaseElementSpec
from mas.application.repositories.operations import (
    CheckoutGitOperation,
    GitCheckout,
    GitWorkspace,
    ResolveGitOperation,
    ResolveGitRevision,
)
from mas.core.element_deps import ElementBuildContext
from mas.core.enums import ResourceCategory
from mas.core.ref.models import ProviderRef
from mas.domain.files import WorkspaceMode
from mas.domain.repositories import GitRevision, RepositoryId
from pydantic import BaseModel, ConfigDict, Field

from .adapter import GitCLIRepository
from .config import GitSettings


class GitRepositoryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    repository: RepositoryId


class GitOperationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: ProviderRef


class GitCheckoutConfig(GitOperationConfig):
    workspace: str = Field(default="work", pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")
    workspace_mode: WorkspaceMode = WorkspaceMode.ISOLATED


class GitRepositoryFactory(BaseFactory[GitRepositoryConfig, GitCLIRepository]):
    def accepts(self, cfg: GitRepositoryConfig, element_type: str) -> bool:
        return element_type == "git_repository"

    def create(self, cfg: GitRepositoryConfig, **dependencies: Any) -> GitCLIRepository:
        deps: ElementBuildContext = dependencies["deps"]
        if deps.execution_ctx is None:
            raise ValueError("Repository access requires execution identity")
        settings = GitSettings.model_validate({})
        binding = settings.repositories.get(cfg.repository)
        if binding is None:
            raise PermissionError("Repository access is not permitted")
        return GitCLIRepository(
            cfg.repository, binding, deps.execution_ctx.context.identity, settings
        )


class ResolveGitFactory(BaseFactory[GitOperationConfig, ResolveGitOperation]):
    def accepts(self, cfg: GitOperationConfig, element_type: str) -> bool:
        return element_type == "resolve_git_revision"

    def create(self, cfg: GitOperationConfig, **dependencies: Any) -> ResolveGitOperation:
        return ResolveGitOperation(dependencies["source"])


class CheckoutGitFactory(BaseFactory[GitCheckoutConfig, CheckoutGitOperation]):
    def accepts(self, cfg: GitCheckoutConfig, element_type: str) -> bool:
        return element_type == "checkout_git_revision"

    def create(self, cfg: GitCheckoutConfig, **dependencies: Any) -> CheckoutGitOperation:
        return CheckoutGitOperation(dependencies["source"], cfg.workspace, cfg.workspace_mode)


class GitRepositorySpec(BaseElementSpec):
    category = ResourceCategory.PROVIDER
    type_key = "git_repository"
    name = "Git repository"
    description = "Access an operator-bound repository with explicit owner admission"
    config_schema = GitRepositoryConfig
    factory_cls = GitRepositoryFactory


class ResolveGitSpec(BaseElementSpec):
    category = ResourceCategory.OPERATION
    type_key = "resolve_git_revision"
    name = "Resolve Git revision"
    description = "Resolve an admitted repository reference to a recorded immutable commit"
    config_schema = GitOperationConfig
    factory_cls = ResolveGitFactory
    input_schema = ResolveGitRevision
    result_schema = GitRevision


class CheckoutGitSpec(BaseElementSpec):
    category = ResourceCategory.OPERATION
    type_key = "checkout_git_revision"
    name = "Checkout Git revision"
    description = "Materialize an exact commit in a new execution-scoped workspace"
    config_schema = GitCheckoutConfig
    factory_cls = CheckoutGitFactory
    input_schema = GitCheckout
    result_schema = GitWorkspace


ELEMENT_SPECIFICATIONS = (GitRepositorySpec, ResolveGitSpec, CheckoutGitSpec)
