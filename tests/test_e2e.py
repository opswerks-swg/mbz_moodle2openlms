"""``e2e run`` against the fake Studio: import, follow-ups, pass, breaks, restore."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from mbz2openlms.check import Rules, predict_gaps
from mbz2openlms.check import known_gaps as gaps
from mbz2openlms.e2e.run import E2E, PLACEHOLDER, flip_answers, scrub_html
from mbz2openlms.openlms.studio import StudioClient
from tests.fake_studio import KEY, FakeStudio

DUE = datetime(2030, 1, 1, tzinfo=UTC)


@pytest.fixture()
def setup(course, olx_copy, olx_archive, tmp_path):
    fake = FakeStudio(olx_copy)
    server = fake.serve()
    url = f"http://127.0.0.1:{server.server_port}"
    accepted = [gaps.KnownGap(f.id, "accepted") for f in predict_gaps(course)]
    log: list[str] = []
    run = E2E(
        client=StudioClient(url, url, "id", "secret"),
        course_key=KEY,
        moodle=course,
        known_gaps=accepted,
        # The leftover link to a file missing from the backup is a real failure; the runbook
        # has the instructor upload it. Allowed here so the run can go on.
        allow_fail={"review-moodle-link|@@PLUGINFILE@@/gone.png"},
        rules=Rules(allowed_hosts={"docs.example.com"}),
        out=tmp_path / "e2e",
        due=DUE,
        log=log.append,
        sleep=lambda _s: None,
    )
    yield fake, run, olx_archive, log
    server.shutdown()


def test_full_run_passes_and_restores_the_course(setup):
    fake, run, archive, log = setup
    assert run.run(archive), "\n".join(log)
    names = [s.name for s in run.steps]
    assert names == [
        "Import into Studio",
        "Checker catches the missing follow-ups",
        "Follow-ups applied through the API",
        "Migrated course passes after the follow-ups",
        "Break: changed answer, not published",
        "Break: changed answer, published",
        "Break: prerequisite below 100%",
        "Break: due date in the past",
        "Course is back to passing",
    ]
    assert fake.prereqs == {"seq_20": ("seq_19", 100.0)}
    assert fake.imports
    assert any("credentials scrubbed" in s.detail and "1 component" in s.detail for s in run.steps)


def test_old_prerequisites_are_cleared_first(setup):
    fake, run, archive, log = setup
    fake.prereqs["seq_20"] = ("seq_19", 100.0)
    fake.is_prereq.add("seq_19")
    run.run(archive, breaks=False)
    assert run.steps[1].ok, run.steps[1].detail  # still reported missing before follow-ups
    assert any("cleared 1 prerequisite" in line for line in log)


def test_unaccepted_failure_stops_the_run(setup):
    fake, run, archive, log = setup
    run.allow_fail = set()
    assert not run.run(archive)
    assert not run.steps[-1].ok
    assert "gone.png" in run.steps[-1].detail


def test_manual_mode_waits_for_a_person(setup):
    fake, run, archive, log = setup
    prompts = []
    run.pause = prompts.append
    run.run(archive, breaks=False)
    assert prompts and "prerequisites at 100%" in prompts[0]
    assert "Follow-ups done in Studio" in [s.name for s in run.steps]


def test_flip_answers():
    assert flip_answers('<c correct="true"/><c correct="false"/>') == (
        '<c correct="false"/><c correct="true"/>'
    )


def test_scrub_html_replaces_the_block_holding_a_credential():
    html = (
        "<p>Keep this.</p><ol><li>Enter your password: <code>Academy@</code>"
        "<code>&lt;user&gt;</code></li><li>Then log in.</li></ol>"
    )
    out = scrub_html(html)
    assert "Academy" not in out
    assert f"<li>{PLACEHOLDER}</li>" in out
    assert "Keep this." in out and "Then log in." in out
