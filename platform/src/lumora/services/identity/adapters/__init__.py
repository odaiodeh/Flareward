"""Outbound identity adapters — implementations of the IdentityProvider port."""

from lumora.services.identity.adapters.dev_provider import DevIdentityProvider
from lumora.services.identity.adapters.noop_provider import NoOpIdentityProvider

__all__ = ["DevIdentityProvider", "NoOpIdentityProvider"]
