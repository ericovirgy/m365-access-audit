"""Load synthetic tenant data from JSON files under fixtures/."""

from __future__ import annotations

import json
from pathlib import Path

from m365_access_audit.models import (
    DirectoryRole,
    Group,
    SubscribedSku,
    TenantSnapshot,
    User,
    parse_iso_utc,
)


def _read_json(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a JSON array")
    return [item for item in data if isinstance(item, dict)]


def load_snapshot(fixtures_dir: Path) -> TenantSnapshot:
    """Read users.json, groups.json, roles.json and skus.json from fixtures_dir."""
    users_raw = _read_json(fixtures_dir / "users.json")
    groups_raw = _read_json(fixtures_dir / "groups.json")
    roles_raw = _read_json(fixtures_dir / "roles.json")
    skus_raw = _read_json(fixtures_dir / "skus.json")

    users = tuple(
        User(
            id=item["id"],
            user_principal_name=item["userPrincipalName"],
            display_name=item["displayName"],
            account_enabled=bool(item["accountEnabled"]),
            user_type=item["userType"],
            created_at=parse_iso_utc(item.get("createdDateTime")),
            last_sign_in_at=parse_iso_utc(item.get("signInActivity", {}).get("lastSignInDateTime")),
            license_sku_ids=tuple(item.get("assignedLicenses", [])),
            department=item.get("department"),
            job_title=item.get("jobTitle"),
        )
        for item in users_raw
        if "id" in item
    )

    groups = tuple(
        Group(
            id=item["id"],
            display_name=item["displayName"],
            group_types=tuple(item.get("groupTypes", [])),
            membership_rule=item.get("membershipRule"),
            member_user_ids=tuple(item.get("members", [])),
        )
        for item in groups_raw
        if "id" in item
    )

    roles = tuple(
        DirectoryRole(
            id=item["id"],
            display_name=item["displayName"],
            member_user_ids=tuple(item.get("members", [])),
        )
        for item in roles_raw
        if "id" in item
    )

    skus = tuple(
        SubscribedSku(
            sku_id=item["id"],
            sku_part_number=item.get("skuPartNumber", item["id"]),
            display_name=item.get("displayName", item.get("skuPartNumber", item["id"])),
        )
        for item in skus_raw
        if "id" in item
    )

    return TenantSnapshot(users=users, groups=groups, roles=roles, skus=skus)
