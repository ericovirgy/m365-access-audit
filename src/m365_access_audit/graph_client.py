"""Microsoft Graph client: client-credentials auth, pagination and throttling.

Read only. Uses msal for the token and plain requests for the calls.
"""

from __future__ import annotations

import os
import time
from typing import Any

import msal
import requests

from m365_access_audit.models import (
    DirectoryRole,
    Group,
    SubscribedSku,
    TenantSnapshot,
    User,
    parse_iso_utc,
)

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
REQUIRED_ENV_VARS = ("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET")

# Graph refuses >999 per page; 500 is the maximum when signInActivity is selected.
USER_PAGE_SIZE = 500
USER_SELECT = (
    "id,userPrincipalName,displayName,accountEnabled,userType,createdDateTime,"
    "signInActivity,assignedLicenses,department,jobTitle"
)
GROUP_SELECT = "id,displayName,groupTypes,membershipRule"
ROLE_SELECT = "id,displayName"
MEMBER_SELECT = "id"

MAX_RETRIES = 5


class GraphClient:
    """Minimal read-only Graph client with just the calls this audit needs."""

    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        *,
        base_url: str = GRAPH_BASE_URL,
        session: requests.Session | None = None,
        access_token: str | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._session = session or requests.Session()
        self._tenant_id = tenant_id
        self._client_id = client_id
        self._client_secret = client_secret
        # The msal application is created lazily: constructing it validates the
        # authority over the network, which must not happen when a token is injected.
        self._app: msal.ConfidentialClientApplication | None = None
        self._token: str | None = access_token

    @classmethod
    def from_env(cls) -> GraphClient:
        """Build a client from the three required environment variables."""
        missing = [name for name in REQUIRED_ENV_VARS if not os.environ.get(name)]
        if missing:
            raise RuntimeError("Missing environment variables: " + ", ".join(missing))
        return cls(
            os.environ["AZURE_TENANT_ID"],
            os.environ["AZURE_CLIENT_ID"],
            os.environ["AZURE_CLIENT_SECRET"],
        )

    def _access_token(self) -> str:
        if self._token is not None:
            return self._token
        if self._app is None:
            self._app = msal.ConfidentialClientApplication(
                self._client_id,
                authority=f"https://login.microsoftonline.com/{self._tenant_id}",
                client_credential=self._client_secret,
            )
        result = self._app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        if "access_token" not in result:
            raise RuntimeError(
                f"Failed to acquire Graph token: {result.get('error_description', result)}"
            )
        self._token = str(result["access_token"])
        return self._token

    def get_json(self, path_or_url: str) -> dict[str, Any]:
        """GET one JSON document, retrying 429 with Retry-After, else exponential backoff."""
        url = path_or_url if path_or_url.startswith("http") else f"{self._base_url}{path_or_url}"
        headers = {"Authorization": f"Bearer {self._access_token()}"}
        for attempt in range(MAX_RETRIES + 1):
            response = self._session.get(url, headers=headers, timeout=60)
            if response.status_code == 429:
                if attempt == MAX_RETRIES:
                    raise RuntimeError(f"Graph throttled {url} beyond {MAX_RETRIES} retries")
                delay = float(response.headers.get("Retry-After") or 0)
                if delay <= 0:
                    delay = float(min(2**attempt, 60))
                time.sleep(delay)
                continue
            if response.status_code >= 400:
                raise RuntimeError(
                    f"Graph returned {response.status_code} for {url}: {response.text[:200]}"
                )
            return response.json()
        raise RuntimeError(f"unreachable: retry loop for {url}")  # pragma: no cover

    def get_all(self, path: str, params: dict[str, str] | None = None) -> list[dict[str, Any]]:
        """GET a collection, following @odata.nextLink until exhausted."""
        items: list[dict[str, Any]] = []
        next_url: str | None = path
        first_page = True
        while next_url:
            if first_page and params:
                separator = "&" if "?" in next_url else "?"
                document = self.get_json(
                    next_url + separator + "&".join(f"{k}={v}" for k, v in params.items())
                )
            else:
                document = self.get_json(next_url)
            first_page = False
            items.extend(document.get("value", []))
            next_url = document.get("@odata.nextLink")
        return items

    def collect_snapshot(self) -> TenantSnapshot:
        """Collect everything the audit needs, read only."""
        skus = tuple(
            SubscribedSku(
                sku_id=str(s["id"]),
                sku_part_number=s.get("skuPartNumber", str(s["id"])),
                display_name=s.get("displayName") or s.get("skuPartNumber", str(s["id"])),
            )
            for s in self.get_all("/subscribedSkus")
        )

        users = tuple(
            User(
                id=u["id"],
                user_principal_name=u.get("userPrincipalName", u["id"]),
                display_name=u.get("displayName", ""),
                account_enabled=bool(u.get("accountEnabled", False)),
                user_type=u.get("userType", "Member"),
                created_at=parse_iso_utc(u.get("createdDateTime")),
                last_sign_in_at=parse_iso_utc(
                    (u.get("signInActivity") or {}).get("lastSignInDateTime")
                ),
                license_sku_ids=tuple(
                    str(licence["skuId"]) for licence in u.get("assignedLicenses") or []
                ),
                department=u.get("department"),
                job_title=u.get("jobTitle"),
            )
            for u in self.get_all("/users", {"$select": USER_SELECT, "$top": str(USER_PAGE_SIZE)})
        )

        groups: list[Group] = []
        for g in self.get_all("/groups", {"$select": GROUP_SELECT}):
            members = self.get_all(
                f"/groups/{g['id']}/members/microsoft.graph.user", {"$select": MEMBER_SELECT}
            )
            groups.append(
                Group(
                    id=g["id"],
                    display_name=g.get("displayName", ""),
                    group_types=tuple(g.get("groupTypes") or []),
                    membership_rule=g.get("membershipRule"),
                    member_user_ids=tuple(m["id"] for m in members),
                )
            )

        roles: list[DirectoryRole] = []
        for r in self.get_all("/directoryRoles", {"$select": ROLE_SELECT}):
            members = self.get_all(
                f"/directoryRoles/{r['id']}/members/microsoft.graph.user",
                {"$select": MEMBER_SELECT},
            )
            roles.append(
                DirectoryRole(
                    id=r["id"],
                    display_name=r.get("displayName", ""),
                    member_user_ids=tuple(m["id"] for m in members),
                )
            )

        return TenantSnapshot(users=users, groups=tuple(groups), roles=tuple(roles), skus=skus)
