"""Owner profile grants are policy values, separate from private runner configuration."""

from typing import Self

from pydantic import Field, model_validator

from flareward.models import Model
from flareward.services.identity.domain import Identity


class ProfileGrant(Model):
    profiles: tuple[str, ...] = Field(min_length=1)
    default_profile: str = Field(min_length=1)

    @model_validator(mode="after")
    def valid_profiles(self) -> Self:
        if (
            self.default_profile not in self.profiles
            or any(not name for name in self.profiles)
            or len(set(self.profiles)) != len(self.profiles)
        ):
            raise ValueError("Profile grant requires unique names and an available default")
        return self


class OwnerProfileRule(Model):
    owner: Identity
    grant: ProfileGrant | None = None


class ProfileAccessPolicy(Model):
    default: ProfileGrant | None = None
    owners: tuple[OwnerProfileRule, ...] = Field(default=(), max_length=1000)

    @model_validator(mode="after")
    def unique_owners(self) -> Self:
        identities = [(rule.owner.type, rule.owner.id) for rule in self.owners]
        if any(not identity[1] for identity in identities) or len(set(identities)) != len(
            identities
        ):
            raise ValueError("Profile rules require unique nonempty owner identities")
        return self
