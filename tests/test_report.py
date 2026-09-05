"""Tests for report rendering and writing."""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from pathlib import Path

from m365_access_audit.findings import collect_findings
from m365_access_audit.fixtures_client import load_snapshot
from m365_access_audit.report import (
    CSV_COLUMNS,
    findings_csv,
    report_markdown,
    write_reports,
)
from tests.conftest import FIXTURES_DIR


def _sample_findings() -> list:
    snapshot = load_snapshot(FIXTURES_DIR)
    return collect_findings(snapshot)


def test_report_contains_summary_sections_and_checklist() -> None:
    findings = _sample_findings()
    text = report_markdown(
        findings,
        source="fixtures",
        inactive_days=90,
        generated_at=datetime(2026, 9, 5, 12, 0, 0, tzinfo=UTC),
    )
    assert text.startswith("# M365 Access Audit report")
    assert "## Summary" in text
    assert "| **Total** | **16** |" in text
    for section in (
        "## INACTIVE",
        "## DISABLED_WITH_LICENCE",
        "## LICENSED_NEVER_SIGNED_IN",
        "## PRIVILEGED_ROLE_MEMBER",
        "## STALE_GUEST",
        "## ORPHANED_ADMIN",
        "## Review checklist",
        "### Sign-off",
    ):
        assert section in text
    assert text.count("- [ ]") == len(findings)
    assert "no em dash" not in text  # guard against accidental test-only text
    assert "\u2014" not in text, "em dash must never appear in the report"


def test_report_no_findings_still_renders() -> None:
    text = report_markdown([], source="fixtures", inactive_days=90)
    assert "No findings." in text
    assert "| **Total** | **0** |" in text


def test_csv_columns_and_rows() -> None:
    findings = _sample_findings()
    text = findings_csv(findings)
    rows = list(csv.reader(io.StringIO(text)))
    assert rows[0] == list(CSV_COLUMNS)
    assert len(rows) == len(findings) + 1


def test_write_reports_uses_timestamped_names(tmp_path: Path) -> None:
    findings = _sample_findings()
    md_path, csv_path = write_reports(
        findings, reports_dir=tmp_path, source="fixtures", inactive_days=90
    )
    assert md_path.parent == tmp_path
    assert md_path.name.startswith("report-") and md_path.suffix == ".md"
    assert csv_path.name.startswith("findings-") and csv_path.suffix == ".csv"
    assert md_path.exists() and csv_path.exists()
    again_md, again_csv = write_reports(
        findings, reports_dir=tmp_path, source="fixtures", inactive_days=90
    )
    assert again_md.name.startswith("report-")
    assert again_csv.name.startswith("findings-")
