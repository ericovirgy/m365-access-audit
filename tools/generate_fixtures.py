"""Generate the synthetic fixtures in fixtures/ so the audit can run without a tenant.

Run from the repository root:  uv run python tools/generate_fixtures.py
The output is committed so the tool works out of the box. All names are fictional.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"

SKUS = [
    {"id": "sku-0001", "skuPartNumber": "SPE_E3", "displayName": "Microsoft 365 E3"},
    {"id": "sku-0002", "skuPartNumber": "SPE_E5", "displayName": "Microsoft 365 E5"},
    {
        "id": "sku-0003",
        "skuPartNumber": "EXCHANGESTANDARD",
        "displayName": "Exchange Online (Plan 1)",
    },
]

DEPARTMENTS = ["Finance", "IT", "Operations", "Communications", "Facilities", "Governance"]
DOMAIN = "contoso-fixture.example"


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def build_users() -> list[dict]:
    today = datetime.now(tz=UTC)
    users: list[dict] = []

    def add(
        uid: str,
        upn_local: str,
        name: str,
        *,
        enabled: bool = True,
        user_type: str = "Member",
        created_days_ago: int = 500,
        last_sign_in_days_ago: int | None = 5,
        licences: list[str] | None = None,
        department: str | None = None,
        job_title: str | None = None,
    ) -> None:
        created = today - timedelta(days=created_days_ago)
        sign_in = (
            today - timedelta(days=last_sign_in_days_ago)
            if last_sign_in_days_ago is not None
            else None
        )
        users.append(
            {
                "id": uid,
                "userPrincipalName": f"{upn_local}@{DOMAIN}" if "@" not in upn_local else upn_local,
                "displayName": name,
                "accountEnabled": enabled,
                "userType": user_type,
                "createdDateTime": iso(created),
                "signInActivity": {"lastSignInDateTime": iso(sign_in)} if sign_in else {},
                "assignedLicenses": licences or [],
                "department": department,
                "jobTitle": job_title,
            }
        )

    # 24 active staff, licensed, recently signed in. Positive source of "no findings".
    staff = [
        ("u001", "alice.martins", "Alice Martins", "Finance", "Finance Manager"),
        ("u002", "bruno.costa", "Bruno Costa", "IT", "Systems Administrator"),
        ("u003", "carla.dias", "Carla Dias", "Communications", "Communications Officer"),
        ("u004", "diego.freitas", "Diego Freitas", "Operations", "Operations Coordinator"),
        ("u005", "elena.silva", "Elena Silva", "Governance", "Governance Officer"),
        ("u006", "felipe.gomes", "Felipe Gomes", "IT", "Support Technician"),
        ("u007", "gabriela.lima", "Gabriela Lima", "Finance", "Accountant"),
        ("u008", "henrique.alves", "Henrique Alves", "Operations", "Logistics Analyst"),
        ("u009", "isabel.ramos", "Isabel Ramos", "Communications", "Designer"),
        ("u010", "joao.pereira", "Joao Pereira", "IT", "Network Engineer"),
        ("u011", "karla.mendes", "Karla Mendes", "Governance", "Records Clerk"),
        ("u012", "lucas.moreira", "Lucas Moreira", "Operations", "Warehouse Operator"),
        ("u013", "mariana.sousa", "Mariana Sousa", "Finance", "Controller"),
        ("u014", "nelson.pinto", "Nelson Pinto", "IT", "Service Desk"),
        ("u015", "olga.cardoso", "Olga Cardoso", "Facilities", "Facilities Assistant"),
        ("u016", "paulo.rocha", "Paulo Rocha", "Operations", "Dispatcher"),
        ("u017", "ana.quaresma", "Ana Quaresma", "Communications", "Content Editor"),
        ("u018", "rita.nogueira", "Rita Nogueira", "Governance", "Compliance Analyst"),
        ("u019", "sergio.antunes", "Sergio Antunes", "IT", "Infrastructure Engineer"),
        ("u020", "teresa.coelho", "Teresa Coelho", "Finance", "AP Clerk"),
        ("u021", "ulisses.marques", "Ulisses Marques", "Operations", "Fleet Coordinator"),
        ("u022", "vitoria.borges", "Vitoria Borges", "Communications", "Press Officer"),
        ("u023", "xico.melo", "Xico Melo", "Facilities", "Maintenance Technician"),
        ("u024", "yara.fontes", "Yara Fontes", "Governance", "Data Protection Officer"),
    ]
    for uid, upn_local, name, dept, title in staff:
        add(
            uid,
            upn_local,
            name,
            created_days_ago=500,
            last_sign_in_days_ago=(int(uid[1:]) % 20) + 1,
            licences=["sku-0001"],
            department=dept,
            job_title=title,
        )

    # u025: licensed, never signed in, only 10 days old: below the 30 day bar, must NOT fire.
    add(
        "u025",
        "nuno.oliveira",
        "Nuno Oliveira",
        created_days_ago=10,
        last_sign_in_days_ago=None,
        licences=["sku-0001"],
        department="Operations",
        job_title="New Hire",
    )

    # u026: active, unlicensed member: must not fire anywhere.
    add(
        "u026",
        "shared.mailbox",
        "Shared Mailbox Account",
        created_days_ago=900,
        last_sign_in_days_ago=3,
        licences=[],
        department="Operations",
        job_title="Shared Mailbox",
    )

    # INACTIVE (2): enabled, licensed, no sign-in for over 90 days.
    add(
        "u101",
        "hugo.neves",
        "Hugo Neves",
        created_days_ago=800,
        last_sign_in_days_ago=140,
        licences=["sku-0001"],
        department="Operations",
        job_title="Storekeeper",
    )
    add(
        "u102",
        "ines.tavares",
        "Ines Tavares",
        created_days_ago=800,
        last_sign_in_days_ago=200,
        licences=["sku-0001"],
        department="Finance",
        job_title="Accountant",
    )

    # DISABLED_WITH_LICENCE (2).
    add(
        "u201",
        "joana.fonseca",
        "Joana Fonseca",
        enabled=False,
        created_days_ago=900,
        last_sign_in_days_ago=120,
        licences=["sku-0001", "sku-0002"],
        department="IT",
        job_title="Former Administrator",
    )
    add(
        "u202",
        "tiago.morais",
        "Tiago Morais",
        enabled=False,
        created_days_ago=700,
        last_sign_in_days_ago=130,
        licences=["sku-0003"],
        department="Sales",
        job_title="Former Sales Representative",
    )

    # LICENSED_NEVER_SIGNED_IN (1): licensed, no sign-in ever, account older than 30 days.
    add(
        "u301",
        "svc.provisioning",
        "Provisioning Service Account",
        created_days_ago=100,
        last_sign_in_days_ago=None,
        licences=["sku-0001"],
        department="IT",
        job_title="Service Account",
    )

    # Privileged accounts.
    add(
        "u401",
        "sofia.aguiar",
        "Sofia Aguiar",
        created_days_ago=1000,
        last_sign_in_days_ago=1,
        licences=["sku-0002"],
        department="IT",
        job_title="Global Administrator",
    )
    add(
        "u402",
        "ricardo.leal",
        "Ricardo Leal",
        created_days_ago=1000,
        last_sign_in_days_ago=120,
        licences=["sku-0002"],
        department="IT",
        job_title="IT Manager",
    )
    add(
        "u403",
        "miguel.torres",
        "Miguel Torres",
        enabled=False,
        created_days_ago=900,
        last_sign_in_days_ago=200,
        licences=[],
        department="IT",
        job_title="Former Systems Administrator",
    )
    add(
        "u404",
        "paula.serra",
        "Paula Serra",
        created_days_ago=600,
        last_sign_in_days_ago=95,
        licences=["sku-0001"],
        department="External",
        job_title="Consultant",
    )

    # Guests: two stale (over 180 days), two fine.
    add(
        "g001",
        "v_collab.partner@outside.example",
        "Vera Outsidecollab",
        user_type="Guest",
        created_days_ago=700,
        last_sign_in_days_ago=260,
        job_title="External Consultant",
    )
    add(
        "g002",
        "v_partner.contact@partner.example",
        "Paulo Partnercontact",
        user_type="Guest",
        created_days_ago=700,
        last_sign_in_days_ago=365,
        job_title="Partner Contact",
    )
    add(
        "g003",
        "v_recent.guest@partner.example",
        "Renata Recentguest",
        user_type="Guest",
        created_days_ago=100,
        last_sign_in_days_ago=10,
        job_title="Partner",
    )
    add(
        "g004",
        "v_never.guest@partner.example",
        "Nuno Neverguest",
        user_type="Guest",
        created_days_ago=400,
        last_sign_in_days_ago=None,
        job_title="Partner",
    )

    return users


def build_groups() -> list[dict]:
    return [
        {
            "id": "grp-001",
            "displayName": "All Staff",
            "groupTypes": [],
            "membershipRule": None,
            "members": [f"u{i:03d}" for i in range(1, 27)] + ["u101", "u102"],
        },
        {
            "id": "grp-002",
            "displayName": "IT Team",
            "groupTypes": [],
            "membershipRule": None,
            "members": ["u002", "u006", "u010", "u014", "u019", "u401"],
        },
        {
            "id": "grp-003",
            "displayName": "Communications Collaboration",
            "groupTypes": ["DynamicMembership"],
            "membershipRule": '(user.department -eq "Communications")',
            "members": ["u003", "u009", "u017", "u022"],
        },
        {
            "id": "grp-004",
            "displayName": "Finance Team",
            "groupTypes": [],
            "membershipRule": None,
            "members": ["u001", "u007", "u013", "u020", "u102"],
        },
        {
            "id": "grp-005",
            "displayName": "Security Responders",
            "groupTypes": ["DynamicMembership"],
            "membershipRule": '(user.jobTitle -contains "Security")',
            "members": [],
        },
        {
            "id": "grp-006",
            "displayName": "External Partners",
            "groupTypes": [],
            "membershipRule": None,
            "members": ["g001", "g002", "g003"],
        },
        {
            "id": "grp-007",
            "displayName": "Facilities Vendors",
            "groupTypes": [],
            "membershipRule": None,
            "members": [],
        },
        {
            "id": "grp-008",
            "displayName": "Project Atlas",
            "groupTypes": [],
            "membershipRule": None,
            "members": ["u004", "u012", "u021", "g003"],
        },
    ]


def build_roles() -> list[dict]:
    return [
        {
            "id": "role-001",
            "displayName": "Global Administrator",
            "members": ["u401", "u403"],
        },
        {
            "id": "role-002",
            "displayName": "Privileged Role Administrator",
            "members": ["u404"],
        },
        {
            "id": "role-003",
            "displayName": "User Administrator",
            "members": ["u401"],
        },
        {
            "id": "role-004",
            "displayName": "Exchange Administrator",
            "members": ["u403"],
        },
    ]


def main() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    files = {
        "users.json": build_users(),
        "groups.json": build_groups(),
        "roles.json": build_roles(),
        "skus.json": SKUS,
    }
    for filename, payload in files.items():
        path = FIXTURES_DIR / filename
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {path} ({len(payload)} records)")


if __name__ == "__main__":
    main()
