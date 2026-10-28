"""``check-report.md`` (shareable: no answer keys) and ``check.json``."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from .. import paths
from ..check import FAIL, GAP, PASS, SKIP, WARN, Report
from . import table, to_json

LABELS = {
    FAIL: "❌ Fail",
    WARN: "⚠️ Warning",
    GAP: "📝 Known gap",
    SKIP: "⏸ Not checked",
    PASS: "✅ Pass",
}


def render(report: Report, generated: datetime | None = None, gaps_file: Path | None = None):
    generated = generated or datetime.now(UTC)
    lines = [
        f"# Check: {report.course}",
        "",
        f"**Result: {'✅ PASS' if report.passed else '❌ FAIL'}**",
        "",
        f"Generated {generated.isoformat(timespec='seconds')}. Moodle: "
        f"`{report.moodle_source}`. OpenLMS: {report.openlms_source}."
        + (f" Known gaps: `{paths.display(gaps_file)}`." if gaps_file else ""),
        "",
    ]
    lines += table(["Status", "Count"], [[LABELS[s], report.count(s)] for s in LABELS])
    for status in (FAIL, WARN, GAP, SKIP):
        found = [f for f in report.findings if f.status == status]
        if found:
            lines += [f"## {LABELS[status]}", ""]
            lines += table(
                ["Check", "Where", "Detail"], [[f.check, f.where, f.detail] for f in found]
            )
    if report.stale_gaps:
        lines += [
            "## Stale known gaps",
            "",
            "Entries in the known-gaps file that match no failing finding: remove them.",
            "",
        ]
        lines += table(["Id", "Reason"], [[g.id, g.reason] for g in report.stale_gaps])
    passed = Counter(f.check for f in report.findings if f.status == PASS)
    lines += ["## Passed", ""]
    lines += table(["Check", "Passed"], [[k, v] for k, v in passed.items()])
    lines += [
        "Every finding, passes included, is in `check.json`. To accept a difference, add its "
        "`id` from there to the known-gaps file with a reason, and have it reviewed.",
        "",
    ]
    return "\n".join(lines)


def write(report: Report, folder: Path, stem: str = "check", gaps_file: Path | None = None):
    folder.mkdir(parents=True, exist_ok=True)
    md = folder / f"{stem}-report.md"
    md.write_text(render(report, gaps_file=gaps_file), encoding="utf-8")
    data = {
        "course": report.course,
        "passed": report.passed,
        "moodle": report.moodle_source,
        "openlms": report.openlms_source,
        "counts": {s: report.count(s) for s in LABELS},
        "findings": report.findings,
        "stale_gaps": report.stale_gaps,
    }
    (folder / f"{stem}.json").write_text(to_json(data), encoding="utf-8")
    return md
