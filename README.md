# m365-access-audit

## What it does

m365-access-audit collects users, groups, directory roles and licence assignments from a Microsoft 365 tenant through Microsoft Graph and flags the accounts a reviewer should look at: inactive accounts, disabled accounts that still hold licences, licensed accounts that never signed in, privileged role members, stale guests and disabled accounts that still hold admin roles. It writes a timestamped Markdown report a reviewer can work through and sign, plus a CSV of the same findings for records. It is read only: the tool never changes anything in the tenant.

## Why I built it

For two and a half years I ran the quarterly, then monthly, access audit of a national organisation's tenant by hand as its sole administrator, checking accounts, permissions and licences against current roles. This tool reproduces that review so it survives staff changes and takes minutes instead of a day.

## Quick start with fixtures

No tenant, no credentials, no Microsoft account needed. From the repository root:

```fish
uv sync
uv run m365-access-audit --source fixtures
```

This reads the synthetic data in `fixtures/` and writes two files into `reports/`:

- `report-<timestamp>.md`: the review report
- `findings-<timestamp>.csv`: one row per finding

Open the report in any Markdown viewer. It ends with a review checklist and a sign-off block.

Other flags:

```fish
uv run m365-access-audit --source fixtures --inactive-days 60 --reports-dir /tmp/audit
```

## Running against a tenant

### 1. Create the app registration

In the Microsoft Entra admin center:

1. Entra ID, App registrations, New registration. Name it, for example, `Access Audit Tool`. Single tenant.
2. Note the Application (client) ID and the Directory (tenant) ID.
3. API permissions, Add a permission, Microsoft Graph, Application permissions. Add exactly these:
   - `User.Read.All`
   - `Group.Read.All`
   - `LicenseAssignment.Read.All`
   - `AuditLog.Read.All`
   - `RoleManagement.Read.Directory`
4. Grant admin consent for the tenant.
5. Certificates and secrets, New client secret. Copy the value now, it is shown once.

The exact reason each permission is needed is documented in `docs/permissions.md`.

### 2. Provide credentials as environment variables

Credentials come only from the environment, never from files or flags:

```fish
set -x AZURE_TENANT_ID "your-tenant-id"
set -x AZURE_CLIENT_ID "your-client-id"
set -x AZURE_CLIENT_SECRET "your-client-secret"
```

`.env.example` shows the same three variables; if you use a `.env` loader it is gitignored.

### 3. Run

```fish
uv run m365-access-audit --source graph
```

Least privilege notes:

- The app gets five read-only application permissions and nothing else. It cannot write to the tenant.
- `LicenseAssignment.Read.All` is the least privileged permission that serves `GET /subscribedSkus`, the only call that needs it. `Directory.Read.All` also works and was the earlier default, but it grants read access to the whole directory; prefer the narrower one.
- `AuditLog.Read.All` exists only for `signInActivity`. If your tenant has no Microsoft Entra ID P1 or P2 licence at all, `signInActivity` is not returned by Graph; the report will then show fewer INACTIVE and STALE_GUEST findings. See `docs/permissions.md`.
- Run it with a short-lived secret, store it in a password manager or secret manager, and rotate it. The app registration itself should be owned by at least two admins so the audit does not depend on one person.

## Findings reference

| Finding | Meaning | Default trigger | Severity | Recommended action |
| --- | --- | --- | --- | --- |
| INACTIVE | Enabled member account with no recent sign-in | No sign-in for more than 90 days, tunable with `--inactive-days` | medium | Contact the owner; disable or delete the account if no longer needed |
| DISABLED_WITH_LICENCE | Disabled account still consuming a licence | `accountEnabled` is false and licences are assigned | medium | Reclaim the licence |
| LICENSED_NEVER_SIGNED_IN | Licence assigned, no sign-in ever | Account older than 30 days, never signed in, licensed | medium | Confirm the account is expected; otherwise disable and reclaim |
| PRIVILEGED_ROLE_MEMBER | Member of a privileged role, always listed | Member of Global Administrator, Privileged Role Administrator, User Administrator, Exchange Administrator, SharePoint Administrator or Security Administrator | medium; high when the account is also INACTIVE | Confirm the role is still required; remove it or move to just-in-time |
| STALE_GUEST | Guest with no recent sign-in | Guest with no sign-in for more than 180 days | medium | Remove the guest if the collaboration has ended |
| ORPHANED_ADMIN | Disabled account still holding an admin role | Privileged role member with `accountEnabled` false | high | Remove the role assignment |

## How this maps to SC-300

- **Identity governance, access reviews**: the whole loop is an access review: the report is the review input, `docs/procedure.md` is the process around it. Maps to "plan, implement and administer access reviews".
- **Manage user authentication and identity**: INACTIVE, DISABLED_WITH_LICENCE and LICENSED_NEVER_SIGNED_IN are account lifecycle checks. Maps to "create, manage and delete users" and licence management.
- **Plan and implement entitlement**: group and licence data collected. Maps to "implement and manage entitlement management" at a reading level; the tool reports, it does not manage.
- **Plan and implement privileged administration**: PRIVILEGED_ROLE_MEMBER and ORPHANED_ADMIN list standing privileged assignments. Maps to "assign directory roles" and "review privileged access".
- **Monitor and maintain**: the report uses `signInActivity` (sign-in activity), which is the same data an access review uses to find stale accounts. Maps to "monitor and maintain identity" with sign-in logs.
- **External identities**: STALE_GUEST covers the guest lifecycle. Maps to "plan, implement and administer external identities".

The tool does not teach you everything on those skills: there is no PIM, no Conditional Access and no remediation here. It is the evidence-gathering half of an access review.

## Limitations

Stated plainly:

- Read only. It reports; it never disables, deletes or unlicenses anything.
- `directoryRoles` returns only roles that have been activated in the tenant; an unactivated role cannot appear in the report.
- Privileged membership is read as direct role membership. PIM-eligible assignments are not visible here; a member active only through PIM still shows as a standing member.
- `signInActivity` requires Microsoft Entra ID P1 or P2 on the tenant. Without it, sign-in dates are missing and INACTIVE, STALE_GUEST and the escalation to high severity under-report. The other findings still work.
- Only the six listed privileged roles are always reported; custom roles and other built-ins are not assessed.
- Group membership is direct; nested group membership is not resolved.
- The Graph path is client-credentials only; there is no delegated, national-cloud or China-cloud support.
- No scheduling, notifications, dashboards or remediation. This is version 0.1 and the scope is deliberate.

## Licence

MIT. See [LICENSE](LICENSE).
