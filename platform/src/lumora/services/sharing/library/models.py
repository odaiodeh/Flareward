"""Legacy sharing cleanup configuration, retained until administrative cutover."""

from pydantic import BaseModel, Field


class ShareCleanupConfig(BaseModel):
    """Configuration for cleaning up old share invites."""

    # Status-specific cleanup rules
    pending_days: int = Field(default=10, description="Delete pending invites after N days")
    declined_days: int = Field(default=7, description="Delete declined invites after N days")
    canceled_days: int = Field(default=7, description="Delete canceled invites after N days")
    expired_days: int = Field(default=1, description="Delete expired invites after N days")

    # Never delete accepted invites (audit trail)
    preserve_accepted: bool = Field(default=True, description="Never delete accepted invites")

    # Batch processing
    batch_size: int = Field(default=1000, description="Process cleanup in batches of N records")

    # Dry run mode
    dry_run: bool = Field(
        default=False, description="Count what would be deleted without actually deleting"
    )


class ShareCleanupResult(BaseModel):
    """Result of a cleanup operation."""

    total_processed: int = 0
    deleted_count: int = 0
    expired_count: int = 0
    pending_count: int = 0
    declined_count: int = 0
    canceled_count: int = 0
    errors: int = 0
    dry_run: bool = False
