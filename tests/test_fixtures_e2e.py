"""End to end tests over the committed synthetic fixtures."""

from __future__ import annotations

from collections import Counter

from m365_access_audit.findings import collect_findings
from m365_access_audit.fixtures_client import load_snapshot
from tests.conftest import FIXTURES_DIR


def test_fixture_files_load() -> None:
    snapshot = load_snapshot(FIXTURES_DIR)
    assert len(snapshot.users) == 39
    assert len(snapshot.groups) == 8
    assert len(snapshot.roles) == 4
    assert len(snapshot.skus) == 3


def test_fixture_shape() -> None:
    snapshot = load_snapshot(FIXTURES_DIR)
    upns = {u.user_principal_name for u in snapshot.users}
    assert len(upns) == len(snapshot.users), "UPNs must be unique"
    assert all(u.user_principal_name.endswith(".example") for u in snapshot.users), (
        "all fixture UPNs must be in the reserved example TLD"
    )
    guests = [u for u in snapshot.users if u.is_guest]
    assert len(guests) == 4
    disabled = [u for u in snapshot.users if not u.account_enabled]
    assert len(disabled) == 3
    dynamic = [g for g in snapshot.groups if g.is_dynamic]
    assert len(dynamic) == 2
    role_names = {r.display_name for r in snapshot.roles}
    assert "Global Administrator" in role_names


def test_findings_over_fixtures() -> None:
    snapshot = load_snapshot(FIXTURES_DIR)
    findings = collect_findings(snapshot)
    counts = Counter(f.finding_type for f in findings)
    # The fixture set is designed so every finding type fires at least once.
    assert counts["INACTIVE"] == 4
    assert counts["DISABLED_WITH_LICENCE"] == 2
    assert counts["LICENSED_NEVER_SIGNED_IN"] == 1
    assert counts["PRIVILEGED_ROLE_MEMBER"] == 5
    assert counts["STALE_GUEST"] == 2
    assert counts["ORPHANED_ADMIN"] == 2
    assert len(findings) == 16


def test_no_real_looking_data() -> None:
    snapshot = load_snapshot(FIXTURES_DIR)
    for user in snapshot.users:
        upn = user.user_principal_name
        assert ".example" in upn, "fixture UPNs must stay in the reserved example TLD"
