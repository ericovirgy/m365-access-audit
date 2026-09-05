"""Tests for the CLI: fixtures mode end to end and graph mode credential guard."""

from __future__ import annotations

from pathlib import Path

import pytest

from m365_access_audit.cli import main


def test_cli_fixtures_mode_writes_reports(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    reports_dir = tmp_path / "reports"
    exit_code = main(
        ["--source", "fixtures", "--reports-dir", str(reports_dir), "--inactive-days", "90"]
    )
    assert exit_code == 0
    files = list(reports_dir.iterdir())
    assert len(files) == 2
    md = next(f for f in files if f.name.startswith("report-"))
    assert "Review checklist" in md.read_text(encoding="utf-8")
    out = capsys.readouterr().out
    assert "Findings: 16" in out


def test_cli_custom_inactive_days_changes_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(Path(__file__).resolve().parents[1])
    reports_dir = tmp_path / "reports"
    exit_code = main(
        ["--source", "fixtures", "--reports-dir", str(reports_dir), "--inactive-days", "30"]
    )
    assert exit_code == 0
    md = next((tmp_path / "reports").glob("report-*.md"))
    assert "Inactive threshold: 30 days" in md.read_text(encoding="utf-8")


def test_cli_graph_mode_missing_env_exits_cleanly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    for name in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(SystemExit) as exc:
        main(["--source", "graph"])
    assert exc.value.code == 2
    assert "Missing environment variables" in capsys.readouterr().err
