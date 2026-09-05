"""Command line entry point for m365-access-audit."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from m365_access_audit.findings import collect_findings
from m365_access_audit.fixtures_client import load_snapshot
from m365_access_audit.models import TenantSnapshot
from m365_access_audit.report import write_reports

DEFAULT_FIXTURES_DIR = Path("fixtures")
DEFAULT_REPORTS_DIR = Path("reports")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="m365-access-audit",
        description=(
            "Automates the periodic access audit of a Microsoft 365 tenant "
            "and produces a report a reviewer can act on."
        ),
    )
    parser.add_argument(
        "--source",
        choices=("graph", "fixtures"),
        default="fixtures",
        help="Where the tenant data comes from (default: fixtures)",
    )
    parser.add_argument(
        "--inactive-days",
        type=int,
        default=90,
        help="Days without sign-in before an enabled account is flagged INACTIVE (default: 90)",
    )
    parser.add_argument(
        "--fixtures-dir",
        type=Path,
        default=DEFAULT_FIXTURES_DIR,
        help="Directory with the synthetic JSON fixtures (default: ./fixtures)",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=DEFAULT_REPORTS_DIR,
        help="Directory where the report files are written (default: ./reports)",
    )
    return parser


def load_graph_snapshot() -> TenantSnapshot:
    """Import GraphClient lazily so fixtures mode never needs the environment variables."""
    import os

    missing = [
        name
        for name in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET")
        if not os.environ.get(name)
    ]
    if missing:
        print(
            "Missing environment variables: " + ", ".join(missing),
            file=sys.stderr,
        )
        raise SystemExit(2)

    from m365_access_audit.graph_client import GraphClient

    client = GraphClient.from_env()
    return client.collect_snapshot()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.source == "graph":
        snapshot = load_graph_snapshot()
        source = "graph"
    else:
        snapshot = load_snapshot(args.fixtures_dir)
        source = f"fixtures ({args.fixtures_dir})"

    findings = collect_findings(snapshot, inactive_days=args.inactive_days)
    md_path, csv_path = write_reports(
        findings,
        reports_dir=args.reports_dir,
        source=source,
        inactive_days=args.inactive_days,
    )

    print(
        f"Collected {len(snapshot.users)} users, {len(snapshot.groups)} groups, "
        f"{len(snapshot.roles)} directory roles."
    )
    print(f"Findings: {len(findings)}")
    print(f"Report:    {md_path}")
    print(f"CSV:       {csv_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
