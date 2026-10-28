"""State shared by the checks: both courses, the findings, and where each Moodle activity was
found in OpenLMS."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from lxml import etree

from ..moodle.model import Course
from ..openlms.model import MigratedCourse, Section, Subsection, Unit
from .findings import Finding
from .review import Rules


@dataclass
class Node:
    """Where an activity is in OpenLMS: a unit, or a whole subsection (book, Moodle subsection)."""

    section: Section
    sub: Subsection
    unit: Unit | None

    @property
    def elements(self) -> list[etree._Element]:
        return [self.unit.xml] if self.unit else [u.xml for u in self.sub.units]

    def find(self, tag: str) -> list[etree._Element]:
        return [el for root in self.elements for el in root.iter(tag)]

    @property
    def where(self) -> str:
        return " › ".join(
            [self.section.name, self.sub.name] + ([self.unit.name] if self.unit else [])
        )


@dataclass
class Context:
    moodle: Course
    openlms: MigratedCourse | None  # None when only predicting gaps from the backup
    rules: Rules
    now: datetime
    findings: list[Finding] = field(default_factory=list)
    nodes: dict[int, Node] = field(default_factory=dict)  # cmid -> where it is
    used_units: set[int] = field(default_factory=set)  # id(Unit)
    used_subs: set[int] = field(default_factory=set)  # id(Subsection)
    # Problem elements already matched. Elements, not id(): lxml proxies are short-lived and
    # their ids get reused; holding them keeps each node's proxy alive and unique.
    used_problems: set[etree._Element] = field(default_factory=set)

    def add(
        self,
        fid: str,
        check: str,
        where: str,
        status: str,
        detail: str,
        fix: dict[str, str] | None = None,
    ) -> None:
        self.findings.append(Finding(fid, check, where, status, detail, fix))
