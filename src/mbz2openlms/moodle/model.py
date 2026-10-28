"""Typed model of a Moodle course backup.

``moodle.reader.read_backup`` builds it. It is the single description of the source course
that the inventory report, the converter and the checker all read; none of them touch the
backup XML directly.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# -- question bank ---------------------------------------------------------------------------


@dataclass
class Answer:
    id: int
    text_html: str
    fraction: float
    feedback_html: str


@dataclass
class Question:
    id: int
    entry_id: int
    category_id: int
    context_id: int | None
    name: str
    qtype: str
    text_html: str
    general_feedback_html: str
    default_mark: float
    tags: list[str]
    tag_ids: list[int]
    answers: list[Answer]
    # The qtype plugin's own settings, e.g. {"single": "1", "shuffleanswers": "1"} for
    # multichoice or {"responseformat": "editor", "attachments": "0"} for essay.
    options: dict[str, str | None]

    @property
    def kind(self) -> str:
        """The qtype, with multichoice split into single and multiple answer."""
        if self.qtype == "multichoice":
            single = self.options.get("single") == "1"
            return "multichoice_single" if single else "multichoice_multi"
        return self.qtype


@dataclass
class Version:
    number: int
    status: str  # ready, hidden, draft
    question: Question


@dataclass
class BankEntry:
    id: int
    category_id: int
    versions: list[Version]

    @property
    def latest(self) -> Question | None:
        """The newest ready version, which is what a quiz uses unless a version is pinned."""
        ready = [v for v in self.versions if v.status == "ready"]
        return max(ready, key=lambda v: v.number).question if ready else None

    def version(self, number: int | None) -> Question | None:
        if number is None:
            return self.latest
        return next((v.question for v in self.versions if v.number == number), None)


@dataclass
class Category:
    id: int
    name: str
    context_id: int | None
    parent: int | None


@dataclass
class QuestionBank:
    categories: dict[int, Category] = field(default_factory=dict)
    entries: dict[int, BankEntry] = field(default_factory=dict)
    tag_names: dict[int, str] = field(default_factory=dict)

    @property
    def version_count(self) -> int:
        return sum(len(e.versions) for e in self.entries.values())

    def latest_questions(self) -> list[Question]:
        return [q for e in self.entries.values() if (q := e.latest)]


# -- activities ------------------------------------------------------------------------------


@dataclass
class Restriction:
    """Moodle access restriction ("availability") of an activity or section."""

    tree: dict[str, Any]
    summary: str

    @property
    def flat(self) -> bool:
        """A plain AND of conditions, with no nested groups."""
        return self.tree.get("op", "&") == "&" and all("type" in c for c in self.conditions)

    @property
    def conditions(self) -> list[dict[str, Any]]:
        return self.tree.get("c", [])

    def completion_cmids(self) -> list[int]:
        """Activities that must be completed (or passed) first."""
        return [
            c["cm"]
            for c in self.conditions
            if c.get("type") == "completion" and c.get("e") in (1, 2) and "cm" in c
        ]

    def dates(self) -> list[tuple[str, int]]:
        """("from" | "until", timestamp) conditions."""
        return [
            ("from" if c.get("d") == ">=" else "until", c["t"])
            for c in self.conditions
            if c.get("type") == "date"
        ]

    def other_types(self) -> list[str]:
        return [c["type"] for c in self.conditions if c.get("type") not in ("completion", "date")]


@dataclass
class Chapter:
    id: int
    pagenum: int
    title: str
    subchapter: bool
    hidden: bool
    content_html: str


@dataclass
class Slot:
    number: int
    page: int
    max_mark: float
    kind: str  # fixed, random, unknown
    # Fixed slots
    entry_id: int | None = None
    pinned_version: int | None = None
    question: Question | None = None
    # Random slots
    filter_key: str | None = None
    filter_tags: list[str] = field(default_factory=list)
    pool: list[Question] = field(default_factory=list)
    unhandled_filters: list[str] = field(default_factory=list)


@dataclass
class RandomGroup:
    """Random slots that draw from the same pool."""

    slots: list[int]
    marks: list[float]
    tags: list[str]
    pool: list[Question]

    @property
    def count(self) -> int:
        return len(self.slots)

    @property
    def sufficient(self) -> bool:
        return len(self.pool) >= self.count


@dataclass
class FeedbackItem:
    id: int
    position: int
    type: str  # multichoice, multichoicerated, textarea, textfield, numeric, label, info, ...
    name: str
    required: bool
    presentation: str
    choice_style: str | None = None  # radio, checkbox, dropdown
    choices: list[str] = field(default_factory=list)

    @property
    def is_agreement(self) -> bool:
        """A single "I agree" checkbox."""
        checkbox = self.type == "multichoice" and self.choice_style == "checkbox"
        return checkbox and len(self.choices) == 1

    @property
    def is_free_text(self) -> bool:
        return self.type in ("textarea", "textfield", "numeric")

    @property
    def is_rating(self) -> bool:
        return self.type in ("multichoice", "multichoicerated") and not self.is_agreement


@dataclass
class FileSubmission:
    max_files: int
    max_bytes: int
    file_types: str


@dataclass
class Detail:
    """Settings every activity has."""

    intro_html: str = ""


@dataclass
class PageDetail(Detail):
    content_html: str = ""


@dataclass
class LabelDetail(Detail):
    pass


@dataclass
class UrlDetail(Detail):
    external_url: str = ""


@dataclass
class BookDetail(Detail):
    chapters: list[Chapter] = field(default_factory=list)


@dataclass
class AssignDetail(Detail):
    activity_html: str = ""
    opens: datetime | None = None
    due: datetime | None = None
    cutoff: datetime | None = None
    grade: float = 0.0  # < 0: a Moodle scale
    submission_types: list[str] = field(default_factory=list)  # onlinetext, file
    file_submission: FileSubmission | None = None
    team_submission: bool = False


@dataclass
class QuizDetail(Detail):
    opens: datetime | None = None
    closes: datetime | None = None
    time_limit_minutes: int = 0
    attempts: int = 0  # 0 = unlimited
    shuffle_answers: bool = False
    questions_per_page: int = 0
    grade: float = 0.0
    sum_grades: float = 0.0
    password_set: bool = False
    subnet_restricted: bool = False
    browser_security: bool = False
    # Bitmasks of when learners may review each part of an attempt (mod/quiz constants).
    review: dict[str, int] = field(default_factory=dict)
    slots: list[Slot] = field(default_factory=list)
    random_groups: list[RandomGroup] = field(default_factory=list)

    @property
    def fixed_slots(self) -> list[Slot]:
        return [s for s in self.slots if s.kind == "fixed"]


@dataclass
class FeedbackDetail(Detail):
    opens: datetime | None = None
    closes: datetime | None = None
    page_after_submit_html: str = ""
    items: list[FeedbackItem] = field(default_factory=list)

    @property
    def questions(self) -> list[FeedbackItem]:
        """Items a learner answers (no labels, page breaks or info)."""
        return [i for i in self.items if i.type not in ("label", "pagebreak", "info")]

    @property
    def is_agreement(self) -> bool:
        """Every question is a single "I agree" checkbox (an integrity agreement)."""
        questions = self.questions
        return bool(questions) and all(i.is_agreement for i in questions)


@dataclass
class GenericDetail(Detail):
    settings: dict[str, str | None] = field(default_factory=dict)


@dataclass
class Activity:
    cmid: int
    modname: str
    title: str
    section_id: int
    context_id: int | None
    visible: bool
    completion: str  # none, manual, automatic
    restriction: Restriction | None
    detail: Detail

    @property
    def where(self) -> str:
        return f"{self.modname} '{self.title}'"


# -- structure, grades, files ----------------------------------------------------------------


@dataclass
class Section:
    id: int
    number: int
    name: str
    summary_html: str
    visible: bool
    restriction: Restriction | None
    # Moodle 5 subsections are sections owned by a "subsection" activity.
    parent_cmid: int | None
    sequence: list[int]


@dataclass
class OutlineItem:
    activity: Activity
    children: list[OutlineItem] = field(default_factory=list)  # a subsection's activities
    section: Section | None = None  # the delegated section of a subsection


@dataclass
class OutlineSection:
    section: Section
    items: list[OutlineItem]

    @property
    def name(self) -> str:
        return self.section.name or f"Section {self.section.number}"


@dataclass
class GradeItem:
    id: int
    item_type: str  # mod, manual, category, course
    module: str | None
    cmid: int | None
    name: str | None
    category_id: int | None
    grade_type: str  # none, value, scale, text
    grade_max: float
    grade_pass: float
    weight_raw: float
    weight_override: bool
    hidden: bool

    @property
    def counts(self) -> bool:
        """Contributes points to the course total."""
        return self.grade_type == "value" and self.grade_max > 0


@dataclass
class Gradebook:
    aggregation: str  # natural, mean, weighted mean, ...
    items: list[GradeItem]
    course_item: GradeItem | None

    def item(self, cmid: int) -> GradeItem | None:
        return next((i for i in self.items if i.cmid == cmid), None)

    def weights(self) -> dict[int, float]:
        """Share of the course grade per activity (cmid), 0..1.

        Natural aggregation (Moodle's default) weighs each item by its maximum grade, unless
        the weight was overridden by hand. Other aggregations use the stored coefficient.
        """
        items = [i for i in self.items if i.counts and i.cmid is not None]
        if self.aggregation != "natural":
            total = sum(i.weight_raw for i in items) or 1.0
            return {i.cmid: i.weight_raw / total for i in items}
        fixed = sum(i.weight_raw for i in items if i.weight_override)
        free = [i for i in items if not i.weight_override]
        total = sum(i.grade_max for i in free)
        return {
            i.cmid: i.weight_raw
            if i.weight_override
            else ((1 - fixed) * i.grade_max / total if total else 0.0)
            for i in items
        }


@dataclass
class File:
    id: int
    context_id: int | None
    component: str | None
    filearea: str | None
    filepath: str
    filename: str
    size: int
    mimetype: str | None
    content_hash: str
    path: Path  # where the content is in the extracted backup
    present: bool


@dataclass
class ContentRef:
    """A link, embedded file or embed found in the course's HTML."""

    kind: str
    tag: str
    url: str
    location: str
    context_id: int | None
    cmid: int | None
    file: str | None = None  # pluginfile: path as written
    present: bool | None = None  # pluginfile: content in the backup


@dataclass
class Source:
    backup_name: str
    moodle_release: str | None
    backup_date: datetime | None
    wwwroot: str | None
    course_id: int | None
    includes_users: bool


@dataclass
class Course:
    source: Source
    fullname: str
    shortname: str
    start: datetime | None
    summary_html: str
    sections: dict[int, Section]
    activities: dict[int, Activity]
    outline: list[OutlineSection]
    bank: QuestionBank
    gradebook: Gradebook
    files: list[File]
    refs: list[ContentRef]

    @property
    def slug(self) -> str:
        """File-system friendly short name, e.g. ``a11-fnd-lnx01``."""
        return re.sub(r"[^a-z0-9._-]+", "-", (self.shortname or "course").lower()).strip("-")

    def items(self) -> Iterator[tuple[OutlineSection, OutlineItem, OutlineItem | None]]:
        """Every outline item in display order, with its section and parent subsection."""
        for section in self.outline:
            for item in section.items:
                yield section, item, None
                for child in item.children:
                    yield section, child, item

    def files_of(self, context_id: int | None) -> list[File]:
        return [f for f in self.files if f.context_id == context_id]

    def file(self, context_id: int | None, name: str) -> File | None:
        """The file a ``@@PLUGINFILE@@/name`` link in ``context_id`` points at."""
        base = name.rsplit("/", 1)[-1]
        return next(
            (f for f in self.files if f.context_id == context_id and f.filename == base), None
        )
