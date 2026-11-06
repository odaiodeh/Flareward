"""One policy resolver for discovery, previews and admitted Program capabilities."""

from mas.core.identity import Identity
from mas.domain.execution.profile_access import ProfileAccessPolicy, ProfileGrant
from mas.domain.execution_preferences import ExecutionProfileCatalog


class ExecutionProfileAccess:
    def __init__(
        self, installed: ExecutionProfileCatalog, policy: ProfileAccessPolicy | None = None
    ) -> None:
        self._installed = ExecutionProfileCatalog.model_validate_json(installed.model_dump_json())
        self._policy = (
            ProfileAccessPolicy.model_validate_json(policy.model_dump_json())
            if policy is not None
            else None
        )
        if self._policy is not None:
            for grant in (self._policy.default, *(rule.grant for rule in self._policy.owners)):
                if grant is not None and not set(grant.profiles) <= set(self._installed.profiles):
                    raise ValueError("Profile policy references uninstalled execution profiles")

    def catalog(self, owner: Identity) -> ExecutionProfileCatalog:
        if not owner.id:
            raise PermissionError("Execution profile access requires an owner")
        if self._policy is None:
            return self._installed.model_copy(deep=True)
        grant: ProfileGrant | None = self._policy.default
        for rule in self._policy.owners:
            if rule.owner.owns(owner):
                grant = rule.grant
                break
        if grant is None:
            raise PermissionError("Execution profiles are not permitted for this owner")
        return ExecutionProfileCatalog(
            profiles=tuple(sorted(grant.profiles)),
            default_profile=grant.default_profile,
            environment_profiles=tuple(
                profile
                for profile in self._installed.environment_profiles
                if profile in grant.profiles
            ),
        )
