"""A migrated course as read back from OpenLMS: the checker's target side.

Read from a Studio export (``export.py``) or the Studio REST APIs (``studio.py``). Nothing here
imports the converter: the checker must not share its assumptions.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from lxml import etree


class MigratedError(Exception):
    pass


@dataclass
class Unit:
    id: str
    name: str
    xml: etree._Element  # the vertical, with its components inline
    # Studio API only (None from an export): learners see the last published version.
    published: bool | None = None
    has_changes: bool | None = None


@dataclass
class Subsection:
    id: str
    name: str
    graded: bool
    format: str | None  # assignment type
    start: str | None
    due: str | None
    time_limited: bool
    prereq: str | None = None  # id of the prerequisite subsection
    prereq_min_score: float | None = None  # percent
    units: list[Unit] = field(default_factory=list)


@dataclass
class Section:
    id: str
    name: str
    subsections: list[Subsection] = field(default_factory=list)


@dataclass
class MigratedCourse:
    source: str
    course_key: str | None
    sections: list[Section]
    graders: dict[str, float]  # assignment type -> weight, 0..1
    cutoff: float | None
    # False for an export: prerequisites live in the milestones tables, not in OLX.
    prereqs_known: bool
    static_files: set[str] = field(default_factory=set)
    # Studio API only: component element -> usage key, so e2e can change it.
    block_ids: dict[etree._Element, str] = field(default_factory=dict)

    def subsections(self) -> Iterator[tuple[Section, Subsection]]:
        for section in self.sections:
            for sub in section.subsections:
                yield section, sub

    def units(self) -> Iterator[tuple[Section, Subsection, Unit]]:
        for section, sub in self.subsections():
            for unit in sub.units:
                yield section, sub, unit

    def subsection(self, sub_id: str | None) -> Subsection | None:
        return next((s for _, s in self.subsections() if s.id == sub_id), None)

    def share(self, sub: Subsection) -> float:
        """The subsection's share of the course grade: its type's weight split evenly."""
        same = [s for _, s in self.subsections() if s.graded and s.format == sub.format]
        return self.graders.get(sub.format or "", 0.0) / max(len(same), 1)
