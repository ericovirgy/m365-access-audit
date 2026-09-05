"""Finding types, severities and detection logic for the access audit."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from m365_access_audit.models import TenantSnapshot, User, now_utc

# Directory roles always reviewed. Values are the exact Graph displayName values.
PRIVILEGED_ROLES: frozenset[str] = frozenset(
    {
        "Global Administrator",
        "Privileged Role Administrator",
        "User Administrator",
        "Exchange Administrator",
        "SharePoint Administrator",
        "Security Administrator",
    }
)

SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"

# Days of account age before LICENSED_NEVER_SIGNED_IN applies.
LICENSED_NEVER_SIGNED_IN_MIN_AGE_DAYS = 30
# Days without sign-in before a guest is considered stale.
STALE_GUEST_DAYS = 180

FINDING_TYPES: tuple[str, ...] = (
    "INACTIVE",
    "DISABLED_WITH_LICENCE",
    "LICENSED_NEVER_SIGNED_IN",
    "PRIVILEGED_ROLE_MEMBER",
    "STALE_GUEST",
    "ORPHANED_ADMIN",
)

RECOMMENDED_ACTIONS: dict[str, str] = {
    "INACTIVE": (
        "Contact the account owner and disable or delete the account if it is no longer needed"
    ),
    "DISABLED_WITH_LICENCE": "Reclaim the licence; a disabled account should hold no licence",
    "LICENSED_NEVER_SIGNED_IN": (
        "Confirm the account is expected; if not, disable it and reclaim the licence"
    ),
    "PRIVILEGED_ROLE_MEMBER": (
        "Confirm the role is still required; remove it or move standing access to just-in-time"
    ),
    "STALE_GUEST": "Remove the guest if the collaboration has ended",
    "ORPHANED_ADMIN": "Remove the role assignment; a disabled account must hold no roles",
}


@dataclass(frozen=True)
class Finding:
    """One actionable result, addressed to a reviewer."""

    finding_type: str
    severity: str
    upn: str
    display_name: str
    detail: str
    recommended_action: str


def _finding(finding_type: str, severity: str, user: User, detail: str) -> Finding:
    return Finding(
        finding_type=finding_type,
        severity=severity,
        upn=user.user_principal_name,
        display_name=user.display_name,
        detail=detail,
        recommended_action=RECOMMENDED_ACTIONS[finding_type],
    )


def _format_days(days: int) -> str:
    return f"{days} days"


def find_inactive(snapshot: TenantSnapshot, inactive_days: int = 90) -> list[Finding]:
    """Enabled member accounts with no sign-in in more than inactive_days.

    Guests are excluded: they are covered by STALE_GUEST with its own threshold.
    """
    now = now_utc()
    cutoff = now - timedelta(days=inactive_days)
    findings: list[Finding] = []
    for user in snapshot.users:
        if user.is_guest or not user.account_enabled or user.last_sign_in_at is None:
            continue
        if user.last_sign_in_at < cutoff:
            days = (now - user.last_sign_in_at).days
            findings.append(
                _finding(
                    "INACTIVE",
                    SEVERITY_MEDIUM,
                    user,
                    f"Enabled account with no sign-in for {_format_days(days)} "
                    f"(threshold: {inactive_days} days)",
                )
            )
    return findings


def find_disabled_with_licence(snapshot: TenantSnapshot) -> list[Finding]:
    """Disabled accounts that still hold licences."""
    findings: list[Finding] = []
    for user in snapshot.users:
        if user.account_enabled or not user.license_sku_ids:
            continue
        names = ", ".join(snapshot.sku_names(user.license_sku_ids))
        findings.append(
            _finding(
                "DISABLED_WITH_LICENCE",
                SEVERITY_MEDIUM,
                user,
                f"Account is disabled but still licensed: {names}",
            )
        )
    return findings


def find_licensed_never_signed_in(snapshot: TenantSnapshot) -> list[Finding]:
    """Licensed accounts older than 30 days that have never signed in."""
    now = now_utc()
    findings: list[Finding] = []
    for user in snapshot.users:
        if not user.license_sku_ids or user.last_sign_in_at is not None:
            continue
        if user.created_at is None:
            continue
        age = (now - user.created_at).days
        if age > LICENSED_NEVER_SIGNED_IN_MIN_AGE_DAYS:
            findings.append(
                _finding(
                    "LICENSED_NEVER_SIGNED_IN",
                    SEVERITY_MEDIUM,
                    user,
                    f"Licence assigned but no sign-in ever; account is {_format_days(age)} old",
                )
            )
    return findings


def _privileged_members(snapshot: TenantSnapshot) -> dict[str, set[str]]:
    """Map each privileged role display name to the user ids assigned to it."""
    assigned: dict[str, set[str]] = {}
    for role in snapshot.roles:
        if role.display_name in PRIVILEGED_ROLES and role.member_user_ids:
            assigned.setdefault(role.display_name, set()).update(role.member_user_ids)
    return assigned


def find_privileged_role_members(snapshot: TenantSnapshot) -> list[Finding]:
    """Every member of a privileged role, always reported.

    Severity is high when the member is an enabled account that is also INACTIVE.
    """
    now = now_utc()
    users_by_id = {user.id: user for user in snapshot.users}
    inactive_ids = {
        user.user_principal_name
        for user in snapshot.users
        if user.account_enabled
        and user.last_sign_in_at is not None
        and user.last_sign_in_at < now - timedelta(days=90)
    }
    findings: list[Finding] = []
    for role_name, member_ids in sorted(_privileged_members(snapshot).items()):
        for user_id in sorted(member_ids):
            user = users_by_id.get(user_id)
            if user is None:
                # Role assignment referencing an object not in the user list: report it anyway.
                findings.append(
                    Finding(
                        finding_type="PRIVILEGED_ROLE_MEMBER",
                        severity=SEVERITY_MEDIUM,
                        upn=user_id,
                        display_name="(user not found)",
                        detail=f"Member of {role_name}; account not found in the user list",
                        recommended_action=RECOMMENDED_ACTIONS["PRIVILEGED_ROLE_MEMBER"],
                    )
                )
                continue
            escalated = user.account_enabled and user.user_principal_name in inactive_ids
            extra = "; account is also inactive" if escalated else ""
            if not user.account_enabled:
                extra = "; account is disabled, see ORPHANED_ADMIN"
            findings.append(
                _finding(
                    "PRIVILEGED_ROLE_MEMBER",
                    SEVERITY_HIGH if escalated else SEVERITY_MEDIUM,
                    user,
                    f"Member of {role_name}{extra}",
                )
            )
    return findings


def find_stale_guests(snapshot: TenantSnapshot) -> list[Finding]:
    """Guests with no sign-in in more than 180 days."""
    now = now_utc()
    cutoff = now - timedelta(days=STALE_GUEST_DAYS)
    findings: list[Finding] = []
    for user in snapshot.users:
        if not user.is_guest or user.last_sign_in_at is None:
            continue
        if user.last_sign_in_at < cutoff:
            days = (now - user.last_sign_in_at).days
            findings.append(
                _finding(
                    "STALE_GUEST",
                    SEVERITY_MEDIUM,
                    user,
                    f"Guest with no sign-in for {_format_days(days)} "
                    f"(threshold: {STALE_GUEST_DAYS} days)",
                )
            )
    return findings


def find_orphaned_admins(snapshot: TenantSnapshot) -> list[Finding]:
    """Privileged role members whose accounts are disabled."""
    users_by_id = {user.id: user for user in snapshot.users}
    findings: list[Finding] = []
    for role_name, member_ids in sorted(_privileged_members(snapshot).items()):
        for user_id in sorted(member_ids):
            user = users_by_id.get(user_id)
            if user is None or user.account_enabled:
                continue
            findings.append(
                _finding(
                    "ORPHANED_ADMIN",
                    SEVERITY_HIGH,
                    user,
                    f"Disabled account still assigned to {role_name}",
                )
            )
    return findings


ALL_CHECKS: tuple[Callable[..., list[Finding]], ...] = (
    find_inactive,
    find_disabled_with_licence,
    find_licensed_never_signed_in,
    find_privileged_role_members,
    find_stale_guests,
    find_orphaned_admins,
)


def collect_findings(snapshot: TenantSnapshot, inactive_days: int = 90) -> list[Finding]:
    """Run every check once and return findings ordered by type, then by UPN."""
    findings = find_inactive(snapshot, inactive_days=inactive_days)
    for check in ALL_CHECKS[1:]:
        findings.extend(check(snapshot))
    type_order = {name: index for index, name in enumerate(FINDING_TYPES)}
    findings.sort(key=lambda f: (type_order[f.finding_type], f.upn))
    return findings
