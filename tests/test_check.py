"""The checker: a faithful conversion gives only the expected findings, and each break in the
migrated course gives exactly the finding that describes it."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from mbz2openlms.check import FAIL, GAP, PASS, SKIP, WARN, KnownGap, Rules, check, predict_gaps
from mbz2openlms.openlms.export import from_export, read_olx

NOW = datetime(2026, 10, 28, tzinfo=UTC)
RULES = Rules(allowed_blocks=set(), blocked_blocks={"lti_consumer"})

# What a faithful conversion of the synthetic course must report, and nothing else.
BASELINE = {
    "unsupported|forum 'Chat'": FAIL,
    "time-limit|quiz 'Exam'": FAIL,
    "qtype|quiz 'Exam' slot 8": FAIL,
    "free-text|feedback 'Survey' item 63": FAIL,
    "restriction-multi|feedback 'Survey'": FAIL,
    "review-moodle-link|@@PLUGINFILE@@/gone.png": FAIL,
    "review-secret|password or key assignment": FAIL,
    "optional-item|feedback 'Agreement' item 52": WARN,
    "after-submit|feedback 'Agreement'": WARN,
    "due|Intro › Upload": WARN,
    "due|Assessment › Agreement": WARN,
    "due|Assessment › Final": WARN,
    "due|assign 'Upload'": WARN,
    "review-host|docs.example.com": WARN,
    "prereq|quiz 'Exam'": SKIP,
}


def run(course, root: Path, **kw):
    return check(course, read_olx(root, "test"), rules_=RULES, now=NOW, **kw)


def not_passing(report) -> dict[str, str]:
    return {f.id: f.status for f in report.findings if f.status != PASS}


def edit(root: Path, rel: str, old: str, new: str, count: int = 1) -> None:
    path = root / rel
    text = path.read_text(encoding="utf-8")
    assert old in text, f"{old!r} not in {rel}"
    path.write_text(text.replace(old, new, count), encoding="utf-8")


def test_faithful_conversion(course, olx_copy):
    report = run(course, olx_copy)
    assert not_passing(report) == BASELINE
    checks = {f.check for f in report.findings if f.status == PASS}
    assert checks >= {"structure", "content", "quizzes", "assignments", "grading", "files"}


def test_reads_the_export_archive_too(course, olx_archive):
    report = check(course, from_export(olx_archive), rules_=RULES, now=NOW)
    assert not_passing(report) == BASELINE


# Each mutation: (file, old text, new text) -> the finding id it must turn to FAIL (or WARN).
MUTATIONS = {
    "missing section": (
        "chapter/chapter_5.xml", 'display_name="Survey"', 'display_name="Other"',
        {
            "section|Survey": FAIL,
            "extra-section|Other": FAIL,
            "activity|feedback 'Survey'": FAIL,
            "extra-unit|Other › Survey › Survey": FAIL,
        },
    ),
    "page text changed": (
        "html/html_Welcome.html", "read everything carefully", "skim it",
        {"text|page 'Welcome'": FAIL},
    ),
    "wrong correct answer": (
        "problem/q_20_101.xml", 'correct="true"', 'correct="false"',
        {"question|quiz 'Exam' slot 2 'Capital'": FAIL},
    ),
    "wrong weight": (
        "problem/q_20_101.xml", 'weight="2"', 'weight="1"',
        {"question|quiz 'Exam' slot 2 'Capital'": FAIL},
    ),
    "wrong short answer": (
        "problem/q_20_104.xml", 'answer="ls"', 'answer="ll"',
        {"question|quiz 'Exam' slot 5 'Command'": FAIL},
    ),
    "wrong number": (
        "problem/q_20_105.xml", 'answer="4"', 'answer="5"',
        {"question|quiz 'Exam' slot 6 'Sum'": FAIL},
    ),
    "bank shows a different count": (
        "itembank/bank_20_1.xml", 'max_count="2"', 'max_count="3"',
        {"bank|quiz 'Exam' random group 1": FAIL},
    ),
    "file upload off": (
        "vertical/unit_13.xml", 'file_upload_response="optional"', 'file_upload_response=""',
        {"submission|assign 'Upload'": FAIL},
    ),
    "agreement box optional": (
        "problem/agreement_19.xml", 'correct="true"', 'correct="false"',
        {"agreement|feedback 'Agreement'": FAIL},
    ),
    "survey question missing": (
        "vertical/unit_30.xml", "The labs helped.", "Something else.",
        {"survey|feedback 'Survey'": FAIL},
    ),
    "pass cutoff": (
        "policies/2026/grading_policy.json", '"Pass": 0.5', '"Pass": 0.6', {"pass-mark": FAIL},
    ),
    "exam ungraded": (
        "sequential/seq_20.xml", 'graded="true"', 'graded="false"', {"grading|quiz 'Exam'": FAIL},
    ),
    "iframe": (
        "html/html_Welcome.html", "</p>", '</p><iframe src="https://evil.example/x"></iframe>',
        {"review-embed|evil.example": FAIL},
    ),
    "inline script": (
        "html/html_Welcome.html", "</p>", "</p><script>alert(1)</script>",
        {"review-script|inline": FAIL},
    ),
    "link back to Moodle": (
        "html/html_Welcome.html", "https://docs.example.com/guide",
        "https://moodle.example.org/mod/quiz/view.php?id=20",
        {"review-moodle-link|https://moodle.example.org/mod/quiz/view.php?id=20": FAIL},
    ),
    "blocked component": (
        "vertical/unit_10.xml", "</vertical>", '<lti_consumer url_name="x"/></vertical>',
        {"review-block|lti_consumer": FAIL},
    ),
    "past due date": (
        "sequential/seq_20.xml", 'graded="true"', 'graded="true" due="2026-01-01T00:00:00Z"',
        {"due|Assessment › Final": FAIL},
    ),
    "credential in an answer": (
        "problem/q_20_103.xml", "The sky is blue.", "The sky is blue. AKIAABCDEFGHIJKLMNOP",
        {"review-secret|AWS access key": FAIL},
    ),
}  # fmt: skip


@pytest.mark.parametrize("name", MUTATIONS)
def test_mutation_is_caught(name, course, olx_copy):
    rel, old, new, expected = MUTATIONS[name]
    edit(olx_copy, rel, old, new)
    found = not_passing(run(course, olx_copy))
    changed = {k: v for k, v in found.items() if BASELINE.get(k) != v}
    # "past due date" turns a baseline warning into a failure.
    assert changed == expected


def test_missing_book_chapter(course, olx_copy):
    edit(olx_copy, "sequential/seq_12.xml", '<vertical url_name="unit_12_2"/>', "")
    found = not_passing(run(course, olx_copy))
    assert found["chapter|book 'Materials' chapter 'Files'"] == FAIL


def test_extra_unit(course, olx_copy):
    edit(
        olx_copy,
        "sequential/seq_12.xml",
        "</sequential>",
        '<vertical url_name="unit_x"/></sequential>',
    )
    (olx_copy / "vertical/unit_x.xml").write_text(
        '<vertical display_name="Stray"><html/></vertical>'
    )
    found = not_passing(run(course, olx_copy))
    assert found["extra-unit|Intro › Materials › Stray"] == FAIL


def test_missing_static_file(course, olx_copy):
    (olx_copy / "static" / "1010_diagram_1.png").unlink()
    found = not_passing(run(course, olx_copy))
    assert found["file|page 'Welcome' content|diagram 1.png"] == FAIL
    assert found["static|1010_diagram_1.png"] == FAIL


def test_missing_bank_problem(course, olx_copy):
    path = olx_copy / "itembank" / "bank_20_1.xml"
    text = path.read_text()
    first = text.index("<problem")
    path.write_text(text[:first] + text[text.index("/>", first) + 2 :])
    found = not_passing(run(course, olx_copy))
    assert found["bank|quiz 'Exam' random group 1"] == FAIL


def test_time_limit_set_passes_and_its_gap_is_no_longer_needed(course, olx_copy):
    edit(olx_copy, "sequential/seq_20.xml", 'graded="true"', 'graded="true" is_time_limited="true"')
    report = run(
        course, olx_copy, gaps_list=[KnownGap("time-limit|quiz 'Exam'", "timed exams off")]
    )
    assert report.by_id("time-limit|quiz 'Exam'").status == PASS
    (stale,) = report.stale_gaps
    assert stale.id == "time-limit|quiz 'Exam'" and "no longer needed" in stale.reason


def test_future_due_dates_pass(course, olx_copy):
    for rel in ("sequential/seq_13.xml", "sequential/seq_19.xml", "sequential/seq_20.xml"):
        edit(olx_copy, rel, 'graded="true"', 'graded="true" due="2027-01-01T00:00:00Z"')
    edit(
        olx_copy,
        "vertical/unit_13.xml",
        "<openassessment ",
        '<openassessment submission_due="2027-01-01T00:00:00Z" ',
    )
    found = not_passing(run(course, olx_copy))
    assert not any(k.startswith("due|") for k in found)


def test_known_gaps_downgrade_and_stale_entries(course, olx_copy):
    gaps = [KnownGap(f.id, "accepted by review") for f in predict_gaps(course)]
    gaps.append(KnownGap("time-limit|quiz 'Gone'", "old"))
    report = run(course, olx_copy, gaps_list=gaps)
    for gap in gaps[:-1]:
        assert report.by_id(gap.id).status == GAP, gap.id
    assert [g.id for g in report.stale_gaps] == ["time-limit|quiz 'Gone'"]
    assert "accepted by review" in report.by_id("time-limit|quiz 'Exam'").detail


def test_predicted_gaps_match_the_inherent_failures(course):
    ids = {f.id for f in predict_gaps(course)}
    assert ids == {
        "unsupported|forum 'Chat'",
        "time-limit|quiz 'Exam'",
        "qtype|quiz 'Exam' slot 8",
        "free-text|feedback 'Survey' item 63",
        "restriction-multi|feedback 'Survey'",
        "optional-item|feedback 'Agreement' item 52",
        "after-submit|feedback 'Agreement'",
    }


def test_allowed_host_is_not_reported(course, olx_copy):
    rules = Rules(allowed_hosts={"docs.example.com"})
    report = check(course, read_olx(olx_copy, "t"), rules_=rules, now=NOW)
    assert report.by_id("review-host|docs.example.com") is None


def test_grading_policy_is_read(olx_copy):
    policy = json.loads((olx_copy / "policies/2026/grading_policy.json").read_text())
    assert {g["type"] for g in policy["GRADER"]} == {"Exam", "Assignment", "Integrity Agreement"}
