"""The pilot course, end to end. Opt-in: M2O_SAMPLE_MBZ=<course 131 backup .mbz>.

Backups are never committed. This runs the converter and the checker on the real course:
first as converted (the runbook's follow-ups are reported), then with the follow-ups applied
to the course as an instructor would in Studio (it must pass with the reviewed known gaps),
then through the e2e harness against a fake Studio.
"""

from __future__ import annotations

import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest

from mbz2openlms.check import FAIL, GAP, PASS, SKIP, WARN, Rules, check
from mbz2openlms.check import known_gaps as gaps
from mbz2openlms.convert import MANUAL, convert
from mbz2openlms.e2e.run import E2E, scrub_html
from mbz2openlms.moodle.reader import open_backup, read_course
from mbz2openlms.olx.writer import pack, write
from mbz2openlms.openlms.export import from_export, read_olx
from mbz2openlms.openlms.studio import StudioClient
from tests.fake_studio import KEY, FakeStudio

NOW = datetime(2026, 10, 28, tzinfo=UTC)
GAPS_FILE = Path(__file__).resolve().parents[1] / "known-gaps" / "a11-fnd-lnx01.toml"
RULES = Rules.load(Path(__file__).resolve().parents[1] / "review-rules.toml")


@pytest.fixture(scope="module")
def converted(sample_mbz, tmp_path_factory):
    out = tmp_path_factory.mktemp("sample")
    with open_backup(sample_mbz) as root:
        course = read_course(root, sample_mbz.name)
        result = convert(course)
        olx = write(result.olx, out)
    return course, result, olx, pack(olx, out / "course.tar.gz")


def statuses(report) -> dict[str, str]:
    return {f.id: f.status for f in report.findings if f.status != PASS}


def test_inventory_matches_the_documented_pilot(converted):
    course, *_ = converted
    assert course.shortname == "A11-FND-LNX01"
    assert len(course.bank.entries) == 57
    quiz = next(a for a in course.activities.values() if a.where == "quiz 'Quiz'").detail
    assert [(g.count, len(g.pool)) for g in quiz.random_groups] == [(19, 20), (3, 7)]
    assert set(course.gradebook.weights().values()) == {0.5}


def test_conversion_lists_the_runbook_follow_ups(converted):
    _course, result, *_ = converted
    manual = " ".join(n.detail for n in result.notes if n.kind == MANUAL)
    assert manual.count("Set prerequisite") == 3
    assert "Possible password or key assignment" in manual
    assert "Relative link" in manual
    assert result.olx.grading_policy["GRADE_CUTOFFS"]["Pass"] == 0.85


def test_check_as_converted_reports_only_the_follow_ups(converted):
    course, _result, _olx, archive = converted
    report = check(course, from_export(archive), gaps.load(GAPS_FILE), RULES, now=NOW)
    found = statuses(report)
    fails = {k for k, v in found.items() if v == FAIL}
    assert fails == {"review-secret|password or key assignment"}
    assert {k for k, v in found.items() if v == SKIP} == {
        "prereq|quiz 'Mock Practical'",
        "prereq|quiz 'Quiz'",
        "prereq|page 'Before you begin'",
        "prereq|quiz 'Practical'",
    }
    assert sum(v == GAP for v in found.values()) == 11
    assert not report.stale_gaps
    # Every quiz question and both problem banks match Moodle.
    quizzes = [f for f in report.findings if f.check == "quizzes"]
    assert quizzes and all(f.status == PASS for f in quizzes)


def test_passes_after_the_runbook_follow_ups(converted, tmp_path):
    """Scrub the credential, drop the broken relative link, set the new run's due dates."""
    course, _result, olx, _archive = converted
    root = Path(shutil.copytree(olx, tmp_path / "course"))
    for html in (root / "html").glob("*.html"):
        text = html.read_text(encoding="utf-8")
        text = scrub_html(text)
        text = re.sub(r'(href|src)="/cdn/[^"]*"', r'\1="#"', text)
        html.write_text(text, encoding="utf-8")
    # Set a future due date wherever the checker asks for one (Studio › Configure › Due date).
    first = check(course, read_olx(root, "converted"), gaps.load(GAPS_FILE), RULES, now=NOW)
    for f in first.findings:
        if f.check == "dates" and f.status != PASS:
            block, attr = f.fix["block"], f.fix["field"]
            kind = "sequential" if attr == "due" else "vertical"
            for path in (root / kind).glob("*.xml"):
                text = path.read_text(encoding="utf-8")
                tag = "<sequential " if kind == "sequential" else "<openassessment "
                if (path.stem == block or f'url_name="{block}"' in text) and tag in text:
                    due = f'{tag}{attr}="2027-01-15T09:00:00Z" '
                    path.write_text(text.replace(tag, due, 1), encoding="utf-8")
    report = check(course, read_olx(root, "after follow-ups"), gaps.load(GAPS_FILE), RULES, now=NOW)
    assert report.passed, [f"{f.id}: {f.detail}" for f in report.findings if f.status == FAIL]
    left = {k: v for k, v in statuses(report).items() if v in (FAIL, WARN)}
    # Only the external hosts the review-rules document has yet to rule on.
    assert all(k.startswith("review-host|") for k in left), left


def test_e2e_flow_on_the_sample(converted, tmp_path):
    course, _result, olx, archive = converted
    fake = FakeStudio(Path(shutil.copytree(olx, tmp_path / "course")))
    server = fake.serve()
    url = f"http://127.0.0.1:{server.server_port}"
    try:
        log: list[str] = []
        run = E2E(
            client=StudioClient(url, url, "id", "secret"),
            course_key=KEY,
            moodle=course,
            known_gaps=gaps.load(GAPS_FILE),
            rules=RULES,
            out=tmp_path / "e2e",
            due=datetime(2030, 1, 1, tzinfo=UTC),
            log=log.append,
            sleep=lambda _s: None,
        )
        assert run.run(archive), "\n".join(log)
        assert fake.prereqs == {
            "seq_701": ("seq_700", 100.0),
            "seq_704": ("seq_703", 100.0),
            "seq_707": ("seq_706", 100.0),
        }
    finally:
        server.shutdown()
