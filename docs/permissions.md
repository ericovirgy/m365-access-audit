# Microsoft Graph permissions

This document lists the exact Microsoft Graph application permissions the audit app registration needs, why each one is needed, and what the tool deliberately does not ask for. Each entry was checked against the Microsoft Graph API documentation for v1.0, per endpoint, at the time of writing (September 2026). Sources are linked per permission.

The app registration should carry exactly these five application permissions and no others.

## Permissions required

### User.Read.All (application)

- **Used for**: `GET /users` with `$select=signInActivity,assignedLicenses,...`
- **Why**: the least privileged application permission that allows reading the full list of user profiles with the properties the audit needs. `User.ReadBasic.All` is not enough: it covers a limited property set that excludes `accountEnabled`, `assignedLicenses` and `signInActivity`.
- **Also covers**: licence SKU ids on each user (`assignedLicenses`), since they are part of the user object read through the same permission.
- **Source**: [List users](https://learn.microsoft.com/en-us/graph/api/user-list?view=graph-rest-1.0), permission table for Application: `User.Read.All, User.ReadWrite.All, Directory.Read.All, Directory.ReadWrite.All`; least privileged is `User.Read.All`.

### Group.Read.All (application)

- **Used for**: `GET /groups` and `GET /groups/{id}/members` (OData cast to `microsoft.graph.user`)
- **Why**: `GroupMember.ReadBasic.All` would allow reading member ids, but only `Group.Read.All` (or `Directory.Read.All`) also returns full group objects such as `groupTypes` and `membershipRule`. Group.Read.All covers both the group objects and their member relationships.
- **Source**: [List groups](https://learn.microsoft.com/en-us/graph/api/group-list?view=graph-rest-1.0) and [List members](https://learn.microsoft.com/en-us/graph/api/group-list-members?view=graph-rest-1.0). For `GET /groups/{id}/members` the least privileged application permission is `GroupMember.ReadBasic.All`, but the audit needs group metadata too, so `Group.Read.All` covers both.

### Directory.Read.All (application)

- **Used for**: `GET /subscribedSkus`
- **Why**: resolves licence SKU ids to human names. The documented least privileged application permission for `GET /subscribedSkus` is `LicenseAssignment.Read.All`; `Directory.Read.All` is listed among the sufficient permissions on the same page. The brief's expected set is kept (Directory.Read.All) since it is also required in practice by other directory reads in some tenants, but if you want to reduce the set further, `LicenseAssignment.Read.All` can replace `Directory.Read.All` for this specific call. This is the only entry where a narrower alternative exists.
- **Source**: [List subscribedSkus](https://learn.microsoft.com/en-us/graph/api/subscribedsku-list?view=graph-rest-1.0). The documented application set is `LicenseAssignment.Read.All` (least privileged), plus `Directory.Read.All, Directory.ReadWrite.All, Organization.Read.All, Organization.ReadWrite.All`.

### AuditLog.Read.All (application)

- **Used for**: the `signInActivity` property on users (`signInActivity.lastSignInDateTime`)
- **Why**: without it, Graph returns an error or omits the property when `$select=signInActivity` is requested. `User.Read.All` alone does not cover it.
- **Licensing caveat, verified**: per the user resource type documentation, `signInActivity` details require a Microsoft Entra ID P1 or P2 license on the tenant and the `AuditLog.Read.All` permission. On a tenant without any P1/P2 licence, sign-in dates will not be returned; the report then under-reports INACTIVE, STALE_GUEST and the high-severity escalation. The tool degrades gracefully: it treats a missing `signInActivity` as "no data" and skips those checks for that account.
- **Source**: [user resource type](https://learn.microsoft.com/en-us/graph/api/resources/user?view=graph-rest-1.0), signInActivity property: "Details for this property require a Microsoft Entra ID P1 or P2 license and the AuditLog.Read.All permission."

### RoleManagement.Read.Directory (application)

- **Used for**: `GET /directoryRoles` and `GET /directoryRoles/{id}/members`
- **Why**: the documented least privileged permission, delegated and application, for listing directory roles and their members. `Directory.Read.All` would also work but is more privileged than needed.
- **Source**: [List directoryRoles](https://learn.microsoft.com/en-us/graph/api/directoryrole-list?view=graph-rest-1.0) and [List members of a directory role](https://learn.microsoft.com/en-us/graph/api/directoryrole-list-members?view=graph-rest-1.0).

## Deliberately not requested

- No write permissions: the tool only performs GET requests; it has no code path that could use a write permission. No `ReadWrite` permission of any kind is requested.
- No `RoleManagement.ReadWrite.Directory`: not needed to read roles and would allow the app to manage role assignments.
- No `User.ReadWrite.All`, `Group.ReadWrite.All`, `Directory.ReadWrite.All`, `Organization.ReadWrite.All`: the app must never be able to create, change or delete directory objects.
- No delegated permissions at all: the tool authenticates as an application with client credentials, with no user context.
- No `AuditLog.ReadBasic.All`: it does not cover the `signInActivity` property on users; `AuditLog.Read.All` is what the user resource documents require for that property.

## Notes and known Graph behaviours verified while writing this

- `GET /directoryRoles` returns only roles that have been activated in the tenant. An unactivated role cannot be listed; this is a Graph behaviour, not a tool limitation, and is stated in the README limitations.
- `GET /users` with `$select=signInActivity` has a maximum page size of 500; the tool uses `$top=500` accordingly.
- `GET /directoryRoles/{id}/members` returns a default page of 1000 and does not support `$top` pagination; tenants with more than 1000 members in one role are outside what 0.1 handles.
- `GET /groups/{id}/members` is documented as not transitive: it returns direct members only. Nested groups are not resolved; stated in the README limitations.
- One known Graph issue: service principals are not listed by `GET /groups/{id}/members` in v1.0. The tool OData-casts to `microsoft.graph.user` anyway because it only needs user members, so this does not affect the audit.

## How to consent

After adding the five application permissions in the app registration, an admin must grant consent for the tenant (Entra admin center, App registrations, your app, API permissions, Grant admin consent). Client credentials flow only sees permissions consented this way.
