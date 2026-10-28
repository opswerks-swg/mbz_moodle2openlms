"""The command line: outputs and exit codes (0 pass, 1 fail, 2 error)."""

from __future__ import annotations

import pytest

from mbz2openlms.cli import main


@pytest.fixture()
def in_tmp(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for name in ("M2O_STUDIO_URL", "M2O_LMS_URL", "M2O_CLIENT_ID", "M2O_CLIENT_SECRET"):
        monkeypatch.delenv(name, raising=False)
    return tmp_path


def test_inventory(backup_mbz, in_tmp):
    assert main(["inventory", str(backup_mbz)]) == 0
    assert (in_tmp / "out/syn-lnx-01/inventory.md").is_file()


def test_convert_then_check_fails_on_the_unfixed_course(backup_mbz, in_tmp, capsys):
    assert main(["convert", str(backup_mbz)]) == 0
    folder = in_tmp / "out/syn-lnx-01"
    archive = folder / "syn-lnx_01-2026.tar.gz"
    assert archive.is_file()
    assert "Manual follow-up in Studio" in (folder / "conversion-report.md").read_text()
    assert main(["check", str(backup_mbz), "--export", str(archive)]) == 1
    assert "FAIL" in capsys.readouterr().out
    assert (folder / "check-report.md").is_file()
    assert (folder / "check.json").is_file()


def test_gaps_init_then_check_uses_it(backup_mbz, in_tmp):
    assert main(["gaps", "init", str(backup_mbz)]) == 0
    gaps = in_tmp / "known-gaps/syn-lnx-01.toml"
    assert "[[gap]]" in gaps.read_text()
    assert main(["gaps", "init", str(backup_mbz)]) == 2  # never overwrites
    main(["convert", str(backup_mbz)])
    archive = in_tmp / "out/syn-lnx-01/syn-lnx_01-2026.tar.gz"
    main(["check", str(backup_mbz), "--export", str(archive)])
    report = (in_tmp / "out/syn-lnx-01/check-report.md").read_text()
    assert "Known gap" in report and "syn-lnx-01.toml" in report


def test_errors_exit_2(backup_mbz, in_tmp):
    bad = in_tmp / "bad.mbz"
    bad.write_text("not a backup")
    assert main(["inventory", str(bad)]) == 2
    assert main(["check", str(backup_mbz)]) == 2  # neither --export nor --course
    assert main(["check", str(backup_mbz), "--export", str(bad)]) == 2
    assert main(["check", str(backup_mbz), "--course", "course-v1:X+Y+Z"]) == 2  # no client
