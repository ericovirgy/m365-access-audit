"""Tests for the fixtures data source."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from m365_access_audit.fixtures_client import load_snapshot
from tests.conftest import FIXTURES_DIR


def test_missing_users_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_snapshot(tmp_path)


def test_non_array_json_raises(tmp_path: Path) -> None:
    (tmp_path / "users.json").write_text(json.dumps({"oops": 1}), encoding="utf-8")
    with pytest.raises(ValueError, match="JSON array"):
        load_snapshot(tmp_path)


def test_unknown_sku_falls_back_to_raw_id(tmp_path: Path) -> None:
    (tmp_path / "users.json").write_text(
        json.dumps(
            [
                {
                    "id": "u1",
                    "userPrincipalName": "u1@contoso-fixture.example",
                    "displayName": "U One",
                    "accountEnabled": False,
                    "userType": "Member",
                    "assignedLicenses": ["sku-unknown"],
                }
            ]
        ),
        encoding="utf-8",
    )
    for name in ("groups.json", "roles.json", "skus.json"):
        (tmp_path / name).write_text("[]", encoding="utf-8")
    snapshot = load_snapshot(tmp_path)
    assert snapshot.sku_names(("sku-unknown",)) == ["sku-unknown"]


def test_full_fixture_set_loads() -> None:
    snapshot = load_snapshot(FIXTURES_DIR)
    assert snapshot.users
    assert snapshot.groups
    assert snapshot.roles
    assert snapshot.skus
