"""Shared test helpers: a fixtures path, a factory for synthetic users and a frozen clock."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from m365_access_audit import findings as findings_module
from m365_access_audit.fixtures_client import load_snapshot
from m365_access_audit.models import (
    DirectoryRole,
    Group,
    SubscribedSku,
    TenantSnapshot,
    User,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"

# Fixed reference instant so day arithmetic in tests is exact.
NOW = datetime(2026, 9, 5, 12, 0, 0, tzinfo=UTC)

SKU = SubscribedSku(sku_id="sku-0001", sku_part_number="SPE_E3", display_name="Microsoft 365 E3")


@pytest.fixture
def snapshot_from_fixtures() -> TenantSnapshot:
    """The committed synthetic fixture set, loaded as a snapshot."""
    return load_snapshot(FIXTURES_DIR)


@pytest.fixture(autouse=True)
def frozen_now(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the clock used by the detection logic so day counting is deterministic."""

    def _fixed_now() -> datetime:
        return NOW

    monkeypatch.setattr(findings_module, "now_utc", _fixed_now)
    monkeypatch.setattr("m365_access_audit.models.now_utc", _fixed_now)


def days_ago(days: float) -> datetime:
    return NOW - timedelta(days=days)


def make_role(role_id: str, display_name: str, members: list[str]) -> DirectoryRole:
    """Build one directory role with the given member user ids."""
    return DirectoryRole(id=role_id, display_name=display_name, member_user_ids=tuple(members))


def make_user(
    uid: str = "u100",
    upn: str = "test.user@contoso-fixture.example",
    *,
    enabled: bool = True,
    guest: bool = False,
    created_days_ago: float = 400,
    last_sign_in_days_ago: float | None = 5,
    licences: tuple[str, ...] = (),
) -> User:
    """Build one synthetic user with dates relative to the frozen NOW."""
    return User(
        id=uid,
        user_principal_name=upn,
        display_name=upn.split("@")[0].replace(".", " ").title(),
        account_enabled=enabled,
        user_type="Guest" if guest else "Member",
        created_at=days_ago(created_days_ago),
        last_sign_in_at=(
            days_ago(last_sign_in_days_ago) if last_sign_in_days_ago is not None else None
        ),
        license_sku_ids=licences,
    )


def make_snapshot(
    users: tuple[User, ...] = (),
    roles: tuple[DirectoryRole, ...] = (),
    groups: tuple[Group, ...] = (),
) -> TenantSnapshot:
    """Build a small snapshot that knows the single test SKU."""
    skus: tuple[SubscribedSku, ...] = (SKU,)
    return TenantSnapshot(users=users, groups=groups, roles=roles, skus=skus)
