"""Data models for tenant objects collected from Microsoft Graph or fixtures.

Only fields the audit needs are modelled. All identifiers are opaque strings;
dates are ISO 8601 strings as returned by Graph (for example 2024-03-01T09:14:22Z).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


def parse_iso_utc(value: str | None) -> datetime | None:
    """Parse an ISO 8601 timestamp into an aware UTC datetime, or None."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def now_utc() -> datetime:
    """Current time as an aware UTC datetime. Kept as a function so tests can reason about it."""
    return datetime.now(tz=UTC)


@dataclass(frozen=True)
class User:
    """A directory user, with the subset of properties the audit uses."""

    id: str
    user_principal_name: str
    display_name: str
    account_enabled: bool
    user_type: str  # "Member" or "Guest"
    created_at: datetime | None
    last_sign_in_at: datetime | None
    license_sku_ids: tuple[str, ...] = field(default_factory=tuple)
    department: str | None = None
    job_title: str | None = None

    @property
    def is_guest(self) -> bool:
        return self.user_type == "Guest"


@dataclass(frozen=True)
class Group:
    """A directory group with its direct user members."""

    id: str
    display_name: str
    group_types: tuple[str, ...]
    membership_rule: str | None
    member_user_ids: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_dynamic(self) -> bool:
        return "DynamicMembership" in self.group_types


@dataclass(frozen=True)
class DirectoryRole:
    """An activated directory role with the user ids assigned to it."""

    id: str
    display_name: str
    member_user_ids: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SubscribedSku:
    """A commercial subscription, used to resolve licence SKU ids to names."""

    sku_id: str
    sku_part_number: str
    display_name: str


@dataclass(frozen=True)
class TenantSnapshot:
    """Everything collected from one tenant, whatever the source."""

    users: tuple[User, ...]
    groups: tuple[Group, ...]
    roles: tuple[DirectoryRole, ...]
    skus: tuple[SubscribedSku, ...]

    def sku_names(self, sku_ids: tuple[str, ...] | list[str]) -> list[str]:
        """Resolve licence SKU ids to display names; unknown ids fall back to the raw id."""
        by_id = {sku.sku_id: sku.display_name for sku in self.skus}
        return [by_id.get(sku_id, sku_id) for sku_id in sku_ids]
