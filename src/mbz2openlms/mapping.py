"""How each Moodle feature maps to OpenLMS (Open edX), and what is lost on the way.

This is the one feature table: the inventory report, the runbook's "what carries over" list
and the known-gaps seed all come from it.

Status values:
  supported  converts with no manual work
  partial    converts, but something changes or needs a manual step
  gap        no equivalent: needs a manual decision or rework
  n/a        not learner-facing (e.g. the question bank activity)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .moodle.model import Activity, AssignDetail, FeedbackDetail, Question, QuizDetail

SUPPORTED, PARTIAL, GAP, NA = "supported", "partial", "gap", "n/a"
_ORDER = [SUPPORTED, NA, PARTIAL, GAP]

ACTIVITIES: dict[str, tuple[str, str, str]] = {
    "subsection": ("Subsection", SUPPORTED, ""),
    "book": ("Subsection with one unit per chapter", SUPPORTED, ""),
    "page": ("Unit with an HTML component", SUPPORTED, ""),
    "label": ("Unit with an HTML component", SUPPORTED, ""),
    "url": ("Unit with a link", SUPPORTED, "The link goes through the review-rules scan."),
    "resource": ("File in Files & Uploads, linked from a unit", SUPPORTED, ""),
    "folder": ("Files in Files & Uploads, listed in a unit", PARTIAL, "Subfolders are flattened."),
    "quiz": ("Graded subsection with problem components", SUPPORTED, ""),
    "assign": (
        "Open Response Assessment (ORA), staff-graded",
        PARTIAL,
        "Staff grade submissions in ORA instead of the Moodle grader.",
    ),
    "feedback": (
        "Survey component (rating questions)",
        PARTIAL,
        "",
    ),
    "choice": ("Poll component", GAP, "Not converted: rebuild as a poll."),
    "forum": ("Discussion topic", GAP, "Not converted; posts never carry over."),
    "scorm": ("SCORM component", GAP, "Not converted: upload the package to the SCORM XBlock."),
    "lti": ("LTI component", GAP, "Not converted; credentials are re-entered and reviewed."),
    "h5pactivity": ("No built-in equivalent", GAP, "Needs an H5P XBlock."),
    "lesson": ("No equivalent", GAP, "Branching lessons need manual redesign."),
    "workshop": ("No equivalent", GAP, "Could be rebuilt as an ORA with a peer step."),
    "glossary": ("No equivalent", GAP, ""),
    "wiki": ("No equivalent", GAP, ""),
    "data": ("No equivalent", GAP, ""),
    "survey": ("No equivalent", GAP, ""),
    "chat": ("No equivalent", GAP, ""),
    "imscp": ("No built-in equivalent", GAP, ""),
    "qbank": ("Not learner-facing (source of quiz questions)", NA, ""),
}

QTYPES: dict[str, tuple[str, str, str]] = {
    "multichoice_single": ("Multiple choice problem", SUPPORTED, ""),
    "multichoice_multi": (
        "Checkboxes problem",
        PARTIAL,
        "Weighted partial credit becomes all-or-nothing.",
    ),
    "truefalse": ("Multiple choice problem (True/False)", SUPPORTED, ""),
    "shortanswer": ("Text input problem", SUPPORTED, "Wildcard (*) answers need a manual fix."),
    "numerical": ("Numerical input problem", SUPPORTED, ""),
    "essay": ("ORA, staff-graded", PARTIAL, "Not auto-graded: staff grade it in ORA."),
    "description": ("HTML component", SUPPORTED, ""),
}
QTYPE_GAP = ("No equivalent", GAP, "Not converted: rebuild by hand.")

# Converted question types, as Question.kind values (used by the converter and the checker).
CONVERTED_QTYPES = set(QTYPES)


@dataclass
class Mapping:
    target: str
    status: str
    notes: list[str] = field(default_factory=list)

    def worsen(self, status: str, note: str = "") -> None:
        if _ORDER.index(status) > _ORDER.index(self.status):
            self.status = status
        if note:
            self.notes.append(note)


def map_question(q: Question) -> tuple[str, str, str]:
    return QTYPES.get(q.kind, QTYPE_GAP)


def map_activity(act: Activity) -> Mapping:
    target, status, note = ACTIVITIES.get(
        act.modname, ("Unknown activity type", GAP, f"No mapping for '{act.modname}'.")
    )
    m = Mapping(target, status, [note] if note else [])
    d = act.detail
    if isinstance(d, QuizDetail):
        _quiz(d, m)
    elif isinstance(d, AssignDetail):
        if d.grade <= 0:
            m.target = "Open Response Assessment (ORA), ungraded"
        if d.file_submission:
            fs = d.file_submission
            m.notes.append(
                f"File upload: up to {fs.max_files} file(s) of {fs.max_bytes // 1024} KB, "
                f"types '{fs.file_types or 'any'}'."
            )
    elif isinstance(d, FeedbackDetail):
        if d.is_agreement:
            m.target = "Checkbox problem, every box required"
        elif not any(i.is_rating for i in d.items):
            m.target = "Not converted (no agreement or rating questions)"
            m.worsen(GAP)
        free = sum(i.is_free_text for i in d.items)
        if free:
            m.worsen(PARTIAL, f"{free} free-text question(s) have no equivalent.")
        if d.page_after_submit_html.strip():
            m.notes.append("The 'page after submit' message has no equivalent.")
        if any(i.is_agreement and not i.required for i in d.items):
            m.notes.append("Optional statements become required.")
    if act.restriction:
        m.worsen(
            PARTIAL,
            f"Access restriction: {act.restriction.summary}. Closest match: a subsection "
            "prerequisite.",
        )
    if not act.visible:
        m.notes.append("Hidden from learners in Moodle.")
    return m


def _quiz(d: QuizDetail, m: Mapping) -> None:
    questions = [s.question for s in d.fixed_slots if s.question]
    for group in d.random_groups:
        questions += group.pool
    kinds = {q.qtype for q in questions}
    if kinds == {"description"}:
        m.target = "Unit with the instructions (no gradable question)"
    elif kinds and kinds <= {"essay", "description"}:
        m.target = "ORA, staff-graded, in a graded subsection"
        m.worsen(PARTIAL)
    for q in questions:
        m.worsen(map_question(q)[1])
    if d.random_groups:
        m.worsen(
            PARTIAL,
            f"{sum(g.count for g in d.random_groups)} random slot(s): a Problem Bank shows "
            "each learner N problems from the pool.",
        )
    if any(s.question is None for s in d.fixed_slots):
        m.worsen(GAP, "Some slots point at questions missing from the backup.")
    if any(not g.sufficient for g in d.random_groups):
        m.worsen(GAP, "A random pool has fewer questions than slots drawing from it.")
    if d.time_limit_minutes:
        m.worsen(PARTIAL, f"Time limit {d.time_limit_minutes} min needs timed exams on OpenLMS.")
    if d.opens or d.closes:
        m.notes.append("Open/close dates belong to the old run: set new dates in Studio.")
    if d.grade <= 0:
        m.notes.append("Quiz grade is 0 in Moodle, so the subsection is ungraded.")
    if d.password_set or d.subnet_restricted or d.browser_security:
        m.worsen(PARTIAL, "Quiz password / network / browser restriction has no equivalent.")
