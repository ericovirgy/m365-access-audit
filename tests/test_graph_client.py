"""Tests for the Graph client: pagination, throttling backoff and snapshot assembly.

All network access is faked with a stub session; no token or tenant is needed.
"""

from __future__ import annotations

from typing import Any

import pytest

from m365_access_audit.graph_client import GROUP_SELECT, ROLE_SELECT, USER_SELECT, GraphClient


class FakeResponse:
    def __init__(
        self, status_code: int, payload: dict[str, Any], headers: dict[str, str] | None = None
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self.text = ""

    def json(self) -> dict[str, Any]:
        return self._payload


class FakeSession:
    """Maps URLs to queued responses, recording every request."""

    def __init__(self) -> None:
        self.routes: dict[str, list[FakeResponse]] = {}
        self.calls: list[str] = []
        self.sleeps: list[float] = []

    def route(self, url: str, responses: list[FakeResponse]) -> None:
        self.routes[url] = responses

    def get(self, url: str, headers: dict[str, str] | None = None, timeout: int | None = None):
        self.calls.append(url)
        queue = self.routes[url]
        if len(queue) > 1:
            return queue.pop(0)
        return queue[0]


def test_get_all_follows_next_link() -> None:
    session = FakeSession()
    client = GraphClient("t", "c", "s", session=session, access_token="tok")  # type: ignore[arg-type]
    session.route(
        "https://graph.microsoft.com/v1.0/users?$select=x",
        [FakeResponse(200, {"value": [{"id": "1"}], "@odata.nextLink": "https://page2"})],
    )
    session.route("https://page2", [FakeResponse(200, {"value": [{"id": "2"}]})])
    assert client.get_all("/users", {"$select": "x"}) == [{"id": "1"}, {"id": "2"}]
    assert session.calls == [
        "https://graph.microsoft.com/v1.0/users?$select=x",
        "https://page2",
    ]


def test_get_json_retries_429_with_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession()
    client = GraphClient("t", "c", "s", session=session, access_token="tok")  # type: ignore[arg-type]
    sleeps: list[float] = []
    monkeypatch.setattr("m365_access_audit.graph_client.time.sleep", lambda s: sleeps.append(s))
    session.route(
        "https://graph.microsoft.com/v1.0/users",
        [
            FakeResponse(429, {}, {"Retry-After": "7"}),
            FakeResponse(429, {}, {"Retry-After": "3"}),
            FakeResponse(200, {"value": []}),
        ],
    )
    assert client.get_all("/users") == []
    assert sleeps == [7.0, 3.0]


def test_get_json_429_exponential_fallback_without_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession()
    client = GraphClient("t", "c", "s", session=session, access_token="tok")  # type: ignore[arg-type]
    sleeps: list[float] = []
    monkeypatch.setattr("m365_access_audit.graph_client.time.sleep", lambda s: sleeps.append(s))
    session.route(
        "https://graph.microsoft.com/v1.0/users",
        [FakeResponse(429, {}), FakeResponse(200, {"value": []})],
    )
    assert client.get_all("/users") == []
    assert sleeps == [1.0]


def test_get_json_gives_up_after_max_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    from m365_access_audit.graph_client import MAX_RETRIES

    session = FakeSession()
    client = GraphClient("t", "c", "s", session=session, access_token="tok")  # type: ignore[arg-type]
    monkeypatch.setattr("m365_access_audit.graph_client.time.sleep", lambda s: None)
    session.route(
        "https://graph.microsoft.com/v1.0/users",
        [FakeResponse(429, {})] * (MAX_RETRIES + 1),
    )
    with pytest.raises(RuntimeError, match="throttled"):
        client.get_all("/users")


def test_http_error_raises() -> None:
    session = FakeSession()
    client = GraphClient("t", "c", "s", session=session, access_token="tok")  # type: ignore[arg-type]
    session.route("https://graph.microsoft.com/v1.0/users", [FakeResponse(403, {})])
    with pytest.raises(RuntimeError, match="403"):
        client.get_all("/users")


def test_missing_env_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(RuntimeError, match="Missing environment variables"):
        GraphClient.from_env()


def test_collect_snapshot_assembles_models(monkeypatch: pytest.MonkeyPatch) -> None:
    session = FakeSession()
    client = GraphClient("t", "c", "s", session=session, access_token="tok")  # type: ignore[arg-type]
    monkeypatch.setattr("m365_access_audit.graph_client.time.sleep", lambda s: None)
    base = "https://graph.microsoft.com/v1.0"
    session.route(
        f"{base}/subscribedSkus",
        [
            FakeResponse(
                200,
                {
                    "value": [
                        {
                            "id": "sku-1",
                            "skuPartNumber": "E3",
                            "displayName": "Microsoft 365 E3",
                        }
                    ]
                },
            )
        ],
    )
    session.route(
        f"{base}/users?$select={USER_SELECT}&$top=500",
        [
            FakeResponse(
                200,
                {
                    "value": [
                        {
                            "id": "u1",
                            "userPrincipalName": "u1@contoso-fixture.example",
                            "displayName": "U One",
                            "accountEnabled": True,
                            "userType": "Member",
                            "createdDateTime": "2024-01-01T00:00:00Z",
                            "signInActivity": {"lastSignInDateTime": "2026-09-01T00:00:00Z"},
                            "assignedLicenses": [{"skuId": "sku-1"}],
                        }
                    ]
                },
            )
        ],
    )
    session.route(
        f"{base}/groups?$select={GROUP_SELECT}",
        [
            FakeResponse(
                200,
                {"value": [{"id": "g1", "displayName": "Group One", "groupTypes": []}]},
            )
        ],
    )
    session.route(
        f"{base}/groups/g1/members/microsoft.graph.user?$select=id",
        [FakeResponse(200, {"value": [{"id": "u1"}]})],
    )
    session.route(
        f"{base}/directoryRoles?$select={ROLE_SELECT}",
        [FakeResponse(200, {"value": [{"id": "r1", "displayName": "Global Administrator"}]})],
    )
    session.route(
        f"{base}/directoryRoles/r1/members/microsoft.graph.user?$select=id",
        [FakeResponse(200, {"value": [{"id": "u1"}]})],
    )
    snapshot = client.collect_snapshot()
    assert len(snapshot.users) == 1
    assert snapshot.users[0].last_sign_in_at is not None
    assert snapshot.users[0].license_sku_ids == ("sku-1",)
    assert snapshot.groups[0].member_user_ids == ("u1",)
    assert snapshot.roles[0].member_user_ids == ("u1",)
    assert snapshot.sku_names(("sku-1",)) == ["Microsoft 365 E3"]
