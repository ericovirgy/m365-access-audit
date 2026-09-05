"""Detection tests: every finding type covered with at least one positive and one negative case."""

from __future__ import annotations

import pytest

from m365_access_audit import findings as F
from m365_access_audit.findings import collect_findings
from tests.conftest import make_role, make_snapshot, make_user


def _roles(*pairs: tuple[str, list[str]]):
    return tuple(
        make_role(role_id=f"r{i}", display_name=name, members=members)
        for i, (name, members) in enumerate(pairs)
    )


# INACTIVE


def test_inactive_positive() -> None:
    user = make_user(upn="stale@x.example", last_sign_in_days_ago=100)
    result = F.find_inactive(make_snapshot((user,)))
    assert [f.upn for f in result] == ["stale@x.example"]
    assert result[0].severity == "medium"
    assert "100 days" in result[0].detail


def test_inactive_negative_recent_signin() -> None:
    user = make_user(upn="fresh@x.example", last_sign_in_days_ago=10)
    assert F.find_inactive(make_snapshot((user,))) == []


def test_inactive_negative_disabled_and_threshold_boundary() -> None:
    disabled = make_user(upn="off@x.example", enabled=False, last_sign_in_days_ago=200)
    on_threshold = make_user(upn="edge@x.example", last_sign_in_days_ago=90)
    guest = make_user(upn="g@x.example", guest=True, last_sign_in_days_ago=200)
    result = F.find_inactive(make_snapshot((disabled, on_threshold, guest)))
    assert result == []


def test_inactive_custom_threshold() -> None:
    user = make_user(upn="edge2@x.example", last_sign_in_days_ago=60)
    assert F.find_inactive(make_snapshot((user,)), inactive_days=30) != []
    assert F.find_inactive(make_snapshot((user,)), inactive_days=90) == []


# DISABLED_WITH_LICENCE


def test_disabled_with_licence_positive() -> None:
    user = make_user(upn="off@x.example", enabled=False, licences=("sku-0001",))
    result = F.find_disabled_with_licence(make_snapshot((user,)))
    assert [f.upn for f in result] == ["off@x.example"]
    assert "Microsoft 365 E3" in result[0].detail


def test_disabled_with_licence_negative() -> None:
    disabled_unlicensed = make_user(upn="off@x.example", enabled=False)
    enabled_licensed = make_user(upn="on@x.example", licences=("sku-0001",))
    result = F.find_disabled_with_licence(make_snapshot((disabled_unlicensed, enabled_licensed)))
    assert result == []


# LICENSED_NEVER_SIGNED_IN


def test_licensed_never_signed_in_positive() -> None:
    user = make_user(
        upn="never@x.example",
        created_days_ago=45,
        last_sign_in_days_ago=None,
        licences=("sku-0001",),
    )
    result = F.find_licensed_never_signed_in(make_snapshot((user,)))
    assert [f.upn for f in result] == ["never@x.example"]


def test_licensed_never_signed_in_negative_young_account() -> None:
    user = make_user(
        upn="new@x.example", created_days_ago=10, last_sign_in_days_ago=None, licences=("sku-0001",)
    )
    assert F.find_licensed_never_signed_in(make_snapshot((user,))) == []


def test_licensed_never_signed_in_negative_unlicensed_or_signed_in() -> None:
    unlicensed = make_user(upn="a@x.example", created_days_ago=99, last_sign_in_days_ago=None)
    signed_in = make_user(
        upn="b@x.example", created_days_ago=99, last_sign_in_days_ago=1, licences=("sku-0001",)
    )
    assert F.find_licensed_never_signed_in(make_snapshot((unlicensed, signed_in))) == []


# PRIVILEGED_ROLE_MEMBER


def test_privileged_positive_and_inactive_escalation() -> None:
    active = make_user(uid="u-act", upn="act@x.example", last_sign_in_days_ago=1)
    inactive = make_user(uid="u-in", upn="in@x.example", last_sign_in_days_ago=120)
    roles = _roles(("Global Administrator", ["u-act"]), ("Security Administrator", ["u-in"]))
    result = F.find_privileged_role_members(make_snapshot((active, inactive), roles=roles))
    by_upn = {f.upn: f for f in result}
    assert by_upn["act@x.example"].severity == "medium"
    assert by_upn["in@x.example"].severity == "high"
    assert "inactive" in by_upn["in@x.example"].detail


def test_privileged_negative_non_privileged_role() -> None:
    user = make_user(uid="u-1", upn="u1@x.example")
    roles = _roles(("Global Reader", ["u-1"]), ("Billing Administrator", ["u-1"]))
    assert F.find_privileged_role_members(make_snapshot((user,), roles=roles)) == []


def test_privileged_disabled_member_cross_reference() -> None:
    disabled_admin = make_user(uid="u-2", upn="da@x.example", enabled=False)
    roles = _roles(("User Administrator", ["u-2"]))
    result = F.find_privileged_role_members(make_snapshot((disabled_admin,), roles=roles))
    assert len(result) == 1
    assert "ORPHANED_ADMIN" in result[0].detail


def test_privileged_member_missing_from_user_list() -> None:
    roles = _roles(("Global Administrator", ["ghost-id"]))
    result = F.find_privileged_role_members(make_snapshot((), roles=roles))
    assert len(result) == 1
    assert result[0].display_name == "(user not found)"


# STALE_GUEST


def test_stale_guest_positive() -> None:
    guest = make_user(upn="g@x.example", guest=True, last_sign_in_days_ago=200)
    result = F.find_stale_guests(make_snapshot((guest,)))
    assert [f.upn for f in result] == ["g@x.example"]
    assert "180 days" in result[0].detail


def test_stale_guest_negative_fresh_or_member() -> None:
    fresh_guest = make_user(upn="fg@x.example", guest=True, last_sign_in_days_ago=30)
    stale_member = make_user(upn="m@x.example", last_sign_in_days_ago=400)
    assert F.find_stale_guests(make_snapshot((fresh_guest, stale_member))) == []


def test_stale_guest_negative_never_signed_in() -> None:
    guest = make_user(upn="ng@x.example", guest=True, last_sign_in_days_ago=None)
    assert F.find_stale_guests(make_snapshot((guest,))) == []


# ORPHANED_ADMIN


def test_orphaned_admin_positive() -> None:
    disabled_admin = make_user(uid="u-3", upn="da@x.example", enabled=False)
    roles = _roles(("Exchange Administrator", ["u-3"]))
    result = F.find_orphaned_admins(make_snapshot((disabled_admin,), roles=roles))
    assert [f.upn for f in result] == ["da@x.example"]
    assert result[0].severity == "high"


def test_orphaned_admin_negative_enabled_or_unrelated() -> None:
    enabled_admin = make_user(uid="u-4", upn="ea@x.example")
    plain_user = make_user(uid="u-5", upn="p@x.example", enabled=False)
    roles = _roles(("Exchange Administrator", ["u-4"]))
    result = F.find_orphaned_admins(make_snapshot((enabled_admin, plain_user), roles=roles))
    assert result == []


# collect_findings


def test_collect_findings_covers_all_types_and_is_sorted() -> None:
    stale = make_user(
        uid="u-a", upn="stale@x.example", last_sign_in_days_ago=300, licences=("sku-0001",)
    )
    disabled_admin = make_user(
        uid="u-b", upn="da@x.example", enabled=False, last_sign_in_days_ago=400
    )
    disabled_licensed = make_user(
        uid="u-e",
        upn="dl@x.example",
        enabled=False,
        last_sign_in_days_ago=400,
        licences=("sku-0001",),
    )
    never_signed_in = make_user(
        uid="u-d",
        upn="never@x.example",
        created_days_ago=100,
        last_sign_in_days_ago=None,
        licences=("sku-0001",),
    )
    stale_guest = make_user(uid="u-c", upn="g@x.example", guest=True, last_sign_in_days_ago=365)
    roles = _roles(("Global Administrator", ["u-b"]))
    users = (stale, disabled_admin, disabled_licensed, never_signed_in, stale_guest)
    snapshot = make_snapshot(users, roles=roles)
    result = collect_findings(snapshot)
    types = [f.finding_type for f in result]
    assert set(types) == set(F.FINDING_TYPES)
    order = list(F.FINDING_TYPES)
    indices = [order.index(t) for t in types]
    assert indices == sorted(indices)


def test_collect_findings_custom_inactive_days() -> None:
    user = make_user(upn="m60@x.example", last_sign_in_days_ago=60)
    snapshot = make_snapshot((user,))
    assert not any(f.finding_type == "INACTIVE" for f in collect_findings(snapshot))
    assert any(f.finding_type == "INACTIVE" for f in collect_findings(snapshot, inactive_days=30))


def test_unrelated_user_has_no_findings() -> None:
    user = make_user(upn="clean@x.example", last_sign_in_days_ago=5)
    assert collect_findings(make_snapshot((user,))) == []


@pytest.mark.parametrize("finding_type", list(F.FINDING_TYPES))
def test_every_finding_type_has_recommended_action(finding_type: str) -> None:
    assert F.RECOMMENDED_ACTIONS[finding_type]
