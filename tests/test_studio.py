"""API mode: the checker reads the course through Studio's REST APIs (a fake Studio here),
which also gives subsection prerequisites and publish state."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from mbz2openlms.check import FAIL, PASS, Rules, check
from mbz2openlms.openlms.model import MigratedError
from mbz2openlms.openlms.studio import StudioClient, from_studio
from tests.fake_studio import KEY, FakeStudio

NOW = datetime(2026, 10, 28, tzinfo=UTC)


@pytest.fixture()
def studio(olx_copy):
    fake = FakeStudio(olx_copy)
    server = fake.serve()
    url = f"http://127.0.0.1:{server.server_port}"
    yield fake, StudioClient(url, url, "id", "secret")
    server.shutdown()


def run(course, client):
    return check(course, from_studio(client, KEY), rules_=Rules(), now=NOW)


def test_api_mode_matches_export_mode_and_checks_prerequisites(course, studio):
    fake, client = studio
    fake.prereqs["seq_20"] = ("seq_19", 100.0)
    report = run(course, client)
    prereq = report.by_id("prereq|quiz 'Exam'")
    assert prereq.status == PASS
    assert prereq.fix == {
        "action": "prereq",
        "subsection": "block-v1:OpsWerks+SYN+2026+type@sequential+block@seq_20",
        "prereq": "block-v1:OpsWerks+SYN+2026+type@sequential+block@seq_19",
    }
    assert report.by_id("file|page 'Welcome' content|diagram 1.png").status == PASS
    assert report.by_id("question|quiz 'Exam' slot 2 'Capital'").status == PASS


@pytest.mark.parametrize(
    ("prereq", "detail"),
    [(None, "OpenLMS prerequisite: none"), (("seq_19", 80.0), "minimum score 80%")],
)
def test_missing_or_partial_prerequisite_fails(course, studio, prereq, detail):
    fake, client = studio
    if prereq:
        fake.prereqs["seq_20"] = prereq
    found = run(course, client).by_id("prereq|quiz 'Exam'")
    assert found.status == FAIL
    assert detail in found.detail


def test_extra_prerequisite_warns(course, studio):
    fake, client = studio
    fake.prereqs["seq_12"] = ("seq_10", 100.0)
    assert run(course, client).by_id("prereq-extra|Materials").status == "warn"


def test_unpublished_unit_fails(course, studio):
    fake, client = studio
    fake.unpublished.add("unit_10")
    found = run(course, client).by_id("unpublished|Intro › Welcome › Welcome")
    assert found.status == FAIL


def test_asset_links_are_read_as_static_files(course, studio, olx_copy):
    fake, client = studio
    migrated = from_studio(client, KEY)
    assert migrated.static_files == {"1010_diagram_1.png"}
    (olx_copy / "static" / "1010_diagram_1.png").unlink()
    report = run(course, client)
    assert report.by_id("file|page 'Welcome' content|diagram 1.png").status == FAIL
    assert report.by_id("static|1010_diagram_1.png").status == FAIL
    assert not any(f.id.startswith("review-relative|") for f in report.findings)


def test_bad_credentials(olx_copy):
    with pytest.raises(MigratedError, match="OAuth token"):
        StudioClient("http://127.0.0.1:9", "http://127.0.0.1:9", "id", "x", timeout=2)
