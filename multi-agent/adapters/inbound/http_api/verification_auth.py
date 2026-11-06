"""Evidence-only credentials do not grant ordinary user or workflow authority."""

import hashlib
import hmac
from collections.abc import Awaitable, Callable, Mapping

from fastapi import HTTPException, Request
from mas.application.verification.models import VerificationAuthority

type EvidenceAuthenticator = Callable[[Request], Awaitable[VerificationAuthority]]


class VerifierAuthenticator:
    def __init__(self, authorities: Mapping[str, tuple[str, VerificationAuthority]]) -> None:
        if len(authorities) > 32:
            raise ValueError("At most 32 verification authorities are supported")
        self._authorities = {
            identifier: (
                bytes.fromhex(digest),
                authority.model_copy(deep=True),
            )
            for identifier, (digest, authority) in authorities.items()
        }
        if any(len(digest) != 32 for digest, _ in self._authorities.values()):
            raise ValueError("Verifier credential hashes must use SHA-256")
        if len({digest for digest, _ in self._authorities.values()}) != len(self._authorities):
            raise ValueError("Verifier credentials must be distinct")
        if any(
            identifier != authority.verifier for identifier, (_, authority) in authorities.items()
        ):
            raise ValueError("Verifier credential identity does not match its authority")

    async def __call__(self, request: Request) -> VerificationAuthority:
        identifier = request.headers.get("X-Verification-Authority", "")
        authorization = request.headers.get("Authorization", "")
        scheme, _, credential = authorization.partition(" ")
        configured = self._authorities.get(identifier)
        digest = hashlib.sha256(credential.encode()).digest()
        expected = configured[0] if configured else bytes(32)
        if (
            scheme.lower() != "bearer"
            or not credential
            or configured is None
            or not hmac.compare_digest(digest, expected)
        ):
            raise HTTPException(401, "Verifier authentication required")
        request.state.verification_authority = identifier
        return configured[1].model_copy(deep=True)
