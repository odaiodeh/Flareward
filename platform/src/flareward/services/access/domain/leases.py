"""Bounded renewable expiry; renewal changes neither credential material nor authority."""

from datetime import datetime, timedelta

from pydantic import AwareDatetime, Field

from flareward.models import Model


class CredentialLease(Model):
    ttl_seconds: int = Field(strict=True, ge=1, le=2_592_000)
    renewable_until: AwareDatetime

    def validate_interval(self, issued_at: datetime, expires_at: datetime) -> None:
        if not issued_at < expires_at <= self.renewable_until <= issued_at + timedelta(days=30):
            raise ValueError("Credential renewal must preserve its bounded issuance interval")

    def renew_at(self, expires_at: datetime) -> datetime:
        return expires_at - timedelta(seconds=self.ttl_seconds / 3)

    def next_expiry(self, now: datetime, expires_at: datetime) -> datetime | None:
        if (
            now >= expires_at
            or expires_at >= self.renewable_until
            or now < self.renew_at(expires_at)
        ):
            return None
        expiry = min(now + timedelta(seconds=self.ttl_seconds), self.renewable_until)
        return expiry if expiry > expires_at else None
