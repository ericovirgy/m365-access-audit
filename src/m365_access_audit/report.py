"""Render the audit results as report.md and findings.csv."""

from __future__ import annotations

import csv
import io
from collections import Counter
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path

from m365_access_audit.findings import (
    FINDING_TYPES,
    Finding,
)

CSV_COLUMNS = (
    "finding_type",
    "severity",
    "upn",
    "display_name",
    "detail",
    "recommended_action",
)

FINDING_DESCRIPTIONS: dict[str, str] = {
    "INACTIVE": "Enabled member accounts with no sign-in above the configured threshold",
    "DISABLED_WITH_LICENCE": "Disabled accounts that still hold one or more licences",
    "LICENSED_NEVER_SIGNED_IN": "Licensed accounts older than 30 days that have never signed in",
    "PRIVILEGED_ROLE_MEMBER": "Members of privileged directory roles, listed on every run",
    "STALE_GUEST": "Guest accounts with no sign-in in more than 180 days",
    "ORPHANED_ADMIN": "Privileged role members whose accounts are disabled",
}


def report_markdown(
    findings: list[Finding],
    *,
    source: str,
    inactive_days: int,
    generated_at: datetime | None = None,
) -> str:
    """Build the full report.md content as a string."""
    generated = generated_at or datetime.now(tz=UTC)
    counts = Counter(f.finding_type for f in findings)
    lines: list[str] = []
    add = lines.append

    add("# M365 Access Audit report")
    add("")
    add(f"- Generated: {generated.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    add(f"- Data source: {source}")
    add(f"- Inactive threshold: {inactive_days} days")
    add(f"- Tool version: {metadata.version('m365-access-audit')}")
    add("")

    add("## Summary")
    add("")
    add("| Finding type | Count |")
    add("| --- | ---: |")
    for finding_type in FINDING_TYPES:
        add(f"| {finding_type} | {counts[finding_type]} |")
    add(f"| **Total** | **{len(findings)}** |")
    add("")

    for finding_type in FINDING_TYPES:
        type_findings = [f for f in findings if f.finding_type == finding_type]
        add(f"## {finding_type}")
        add("")
        add(FINDING_DESCRIPTIONS[finding_type] + ".")
        if type_findings:
            add("")
            add("| Severity | UPN | Name | Detail |")
            add("| --- | --- | --- | --- |")
            for f in type_findings:
                add(f"| {f.severity} | `{f.upn}` | {f.display_name} | {f.detail} |")
        else:
            add("")
            add("No findings.")
        add("")

    add("## Review checklist")
    add("")
    add("Reviewer: complete every line and sign at the bottom. Keep this report as evidence.")
    add("")
    for finding in findings:
        add(
            f"- [ ] {finding.finding_type} (severity: {finding.severity}), "
            f"`{finding.upn}`: {finding.recommended_action}"
        )
    add("")
    add("### Sign-off")
    add("")
    add("| Role | Name | Date | Signature |")
    add("| --- | --- | --- | --- |")
    add("| Reviewer | | | |")
    add("| Approver | | | |")
    add("")
    return "\n".join(lines)


def findings_csv(findings: list[Finding]) -> str:
    """Build findings.csv content as a string."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_COLUMNS)
    for f in findings:
        writer.writerow(
            [
                f.finding_type,
                f.severity,
                f.upn,
                f.display_name,
                f.detail,
                f.recommended_action,
            ]
        )
    return buffer.getvalue()


def write_reports(
    findings: list[Finding],
    *,
    reports_dir: Path,
    source: str,
    inactive_days: int,
) -> tuple[Path, Path]:
    """Write report.md and findings.csv into reports_dir with a timestamp prefix."""
    generated_at = datetime.now(tz=UTC)
    stamp = generated_at.strftime("%Y%m%d-%H%M%S")
    reports_dir.mkdir(parents=True, exist_ok=True)
    md_path = reports_dir / f"report-{stamp}.md"
    csv_path = reports_dir / f"findings-{stamp}.csv"
    md_path.write_text(
        report_markdown(
            findings, source=source, inactive_days=inactive_days, generated_at=generated_at
        ),
        encoding="utf-8",
    )
    csv_path.write_text(findings_csv(findings), encoding="utf-8")
    return md_path, csv_path
