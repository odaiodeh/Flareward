"""Outbound identity adapters — implementations of the IdentityProvider port."""

from flareward.services.identity.adapters.dev_provider import DevIdentityProvider
from flareward.services.identity.adapters.noop_provider import NoOpIdentityProvider

__all__ = ["DevIdentityProvider", "NoOpIdentityProvider"]
