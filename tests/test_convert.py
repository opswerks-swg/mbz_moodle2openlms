"""Converting the synthetic course to OLX."""

from __future__ import annotations

import json
import tarfile

import pytest
from lxml import etree

from mbz2openlms.convert import MANUAL, Options, convert
from mbz2openlms.olx.writer import pack, write


@pytest.fixture()
def result(course):
    return convert(course, Options())


def _xml(path):
    return etree.parse(str(path)).getroot()


def test_structure(result):
    olx = result.olx
    assert [s.display_name for s in olx.sections] == ["Intro", "Assessment", "Survey"]
    intro = [s.display_name for s in olx.sections[0].subsections]
    # Summary, consecutive simple items share a subsection, then one per activity.
    assert intro == ["Overview", "Welcome", "Materials", "Upload"]
    assessment = [s.display_name for s in olx.sections[1].subsections]
    # "Final" is split: the exam is gated on the agreement.
    assert assessment == ["Agreement", "Final", "Practice"]


def test_book_gives_one_unit_per_visible_chapter(result):
    materials = result.olx.sections[0].subsections[2]
    assert [u.display_name for u in materials.units] == ["Basics", "Files"]


def test_written_olx_is_well_formed_and_every_problem_has_an_answer(result, tmp_path):
    root = write(result.olx, tmp_path)
    for path in root.rglob("*.xml"):
        _xml(path)  # raises on malformed XML
    for path in (root / "problem").glob("*.xml"):
        el = _xml(path)
        correct = el.xpath(".//choice[@correct='true'] | .//stringresponse | .//numericalresponse")
        assert correct, path.name


def test_random_questions_become_a_problem_bank(result, tmp_path):
    root = write(result.olx, tmp_path)
    (bank,) = [_xml(p) for p in (root / "itembank").glob("*.xml")]
    assert bank.get("max_count") == "2"
    assert len(bank.findall("problem")) == 3


def test_agreement_is_a_graded_zero_weight_checkbox_problem(result):
    agreement = result.olx.sections[1].subsections[0]
    assert agreement.attrs == {"graded": "true", "format": "Integrity Agreement"}
    graders = {g["type"]: g["weight"] for g in result.olx.grading_policy["GRADER"]}
    assert graders["Integrity Agreement"] == 0.0
    assert graders["Exam"] == pytest.approx(2 / 3, abs=1e-4)
    assert graders["Assignment"] == pytest.approx(1 / 3, abs=1e-4)


def test_pass_cutoff_from_matching_pass_marks(result):
    assert result.olx.grading_policy["GRADE_CUTOFFS"]["Pass"] == 0.5


def test_assignment_is_an_ora(result):
    upload = result.olx.sections[0].subsections[3]
    (ora,) = [c for u in upload.units for c in u.components]
    el = ora.content
    assert el.tag == "openassessment"
    assert el.get("file_upload_type") == "custom"
    assert el.get("white_listed_file_types") == "pdf"
    assert el.get("allow_multiple_files") == "True"
    assert el.get("text_response") == "required"
    points = max(int(o.get("points")) for o in el.iter("option"))
    assert points == 50


def test_survey_from_rating_questions(result):
    (survey,) = [c for c in result.olx.components() if c.block_type == "survey"]
    assert [q[1]["label"] for q in json.loads(survey.content.get("questions"))] == [
        "The pace was right.",
        "The labs helped.",
    ]
    assert result.olx.policy["advanced_modules"] == ["openassessment", "survey"]


def test_manual_follow_ups(result):
    manual = [f"{n.where}: {n.detail}" for n in result.notes if n.kind == MANUAL]
    text = "\n".join(manual)
    assert "Set prerequisite 'Agreement' with minimum score 100%" in text
    assert "Possible password or key assignment" in text
    assert "Embedded file 'gone.png' is not in the backup" in text
    assert "Link to another Moodle item ($@QUIZVIEWBYID*20@$)" in text
    assert "'forum' activities are not converted" in text
    assert "Question type 'match' is not converted" in text
    assert "Free-text question not converted: 'What would you change?'" in text
    assert "OpenLMS allows one prerequisite per subsection" in text  # the survey: two


def test_dates_are_left_out_by_default(result):
    subs = [s for c in result.olx.sections for s in c.subsections]
    assert not any("due" in s.attrs or "start" in s.attrs for s in subs)
    assert ("quiz 'Exam'", "opens") in {(w, what) for w, what, _ in result.dates}


def test_keep_dates_and_timed_exams(course):
    result = convert(course, Options(keep_dates=True, timed_exams=True))
    exam = result.olx.sections[1].subsections[1]
    assert exam.attrs["start"] == "2026-07-17T08:00:00Z"
    assert exam.attrs["is_time_limited"] == "true"
    assert exam.attrs["default_time_limit_minutes"] == "30"


def test_embedded_file_is_uploaded_and_linked(result, tmp_path):
    root = write(result.olx, tmp_path)
    assert [p.name for p in (root / "static").iterdir()] == ["1010_diagram_1.png"]
    welcome = next((root / "html").glob("html_Welcome*.html")).read_text()
    assert "/static/1010_diagram_1.png" in welcome
    assert "$@QUIZVIEWBYID" not in welcome


def test_archive_has_one_course_folder(result, tmp_path):
    archive = pack(write(result.olx, tmp_path), tmp_path / "c.tar.gz")
    with tarfile.open(archive) as tf:
        assert {n.split("/")[0] for n in tf.getnames()} == {"course"}
