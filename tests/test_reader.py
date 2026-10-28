"""Reading a Moodle backup into the typed model."""

from __future__ import annotations

import io
import tarfile

import pytest

from mbz2openlms.moodle.model import AssignDetail, FeedbackDetail, QuizDetail
from mbz2openlms.moodle.reader import read_backup
from mbz2openlms.safe.archive import ArchiveError


def test_reads_course_and_source(course):
    assert course.fullname == "Synthetic Linux"
    assert course.slug == "syn-lnx-01"
    assert course.source.includes_users is False
    assert course.source.wwwroot == "https://moodle.example.org"


def test_outline_follows_the_parent_sequence_not_section_numbers(course):
    names = [s.name for s in course.outline]
    assert names == ["Intro", "Assessment", "Survey"]
    assessment = course.outline[1]
    assert [i.activity.title for i in assessment.items] == ["Final", "Practice"]
    assert [c.activity.title for c in assessment.items[0].children] == ["Agreement", "Exam"]


def test_question_bank_counts_entries_not_versions(course):
    assert len(course.bank.entries) == 13
    assert course.bank.version_count == 14


def test_fixed_slot_pinned_to_an_old_version(course):
    practice = course.activities[21].detail
    assert isinstance(practice, QuizDetail)
    assert practice.slots[0].question.name == "Old"


def test_random_pool_skips_hidden_and_untagged(course):
    exam = course.activities[20].detail
    (group,) = exam.random_groups
    assert group.count == 2
    assert group.tags == ["Easy"]
    assert sorted(q.name for q in group.pool) == ["Easy 0", "Easy 1", "Easy 2"]
    assert group.sufficient


def test_question_kinds(course):
    exam = course.activities[20].detail
    kinds = [s.question.kind for s in exam.fixed_slots]
    assert kinds == [
        "description",
        "multichoice_single",
        "multichoice_multi",
        "truefalse",
        "shortanswer",
        "numerical",
        "essay",
        "match",
    ]
    numerical = exam.fixed_slots[5].question
    assert numerical.options["tolerance"] == "0.1"


def test_restrictions(course):
    exam = course.activities[20]
    assert exam.restriction.completion_cmids() == [19]
    assert exam.restriction.summary == "'Agreement' is complete"
    survey = course.activities[30]
    assert survey.restriction.completion_cmids() == [20, 13]


def test_feedback_kinds(course):
    agreement = course.activities[19].detail
    assert isinstance(agreement, FeedbackDetail) and agreement.is_agreement
    survey = course.activities[30].detail
    assert not survey.is_agreement
    assert [i.is_rating for i in survey.questions] == [True, True, False]


def test_assignment(course):
    d = course.activities[13].detail
    assert isinstance(d, AssignDetail)
    assert d.submission_types == ["file", "onlinetext"]
    assert d.file_submission.max_files == 2
    assert d.grade == 50


def test_gradebook_natural_weights(course):
    weights = course.gradebook.weights()
    assert weights == pytest.approx({13: 50 / 150, 20: 100 / 150})


def test_files_and_refs(course):
    present = {f.filename: f.present for f in course.files}
    assert present == {"diagram 1.png": True, "gone.png": False}
    kinds = {(r.kind, r.file, r.present) for r in course.refs if r.kind == "pluginfile"}
    assert kinds == {("pluginfile", "diagram 1.png", True), ("pluginfile", "gone.png", False)}
    assert any(r.kind == "moodle_link" for r in course.refs)


def test_reads_an_mbz_file(backup_mbz):
    assert read_backup(backup_mbz).shortname == "SYN-LNX 01"


def test_rejects_path_traversal(tmp_path):
    bad = tmp_path / "bad.mbz"
    with tarfile.open(bad, "w:gz") as tf:
        info = tarfile.TarInfo("../escape.txt")
        info.size = 2
        tf.addfile(info, io.BytesIO(b"hi"))
    with pytest.raises(ArchiveError, match="Unsafe"):
        read_backup(bad)


def test_rejects_a_non_backup(tmp_path):
    other = tmp_path / "x.mbz"
    other.write_text("hello")
    with pytest.raises(ArchiveError):
        read_backup(other)
