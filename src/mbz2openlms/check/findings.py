"""Findings: one result of one comparison, with a stable id."""

from __future__ import annotations

from dataclasses import dataclass, field

PASS, FAIL, WARN, GAP, SKIP = "pass", "fail", "warn", "known gap", "not checked"
ORDER = [FAIL, WARN, GAP, SKIP, PASS]


@dataclass
class Finding:
    # Stable across runs, e.g. "time-limit|quiz 'Quiz'", so a known-gaps file can list it.
    id: str
    check: str  # structure, content, quizzes, assignments, grading, prerequisites, ...
    where: str
    status: str
    detail: str
    # For a setting the runbook asks for (prerequisite, due date): the ids of the blocks it
    # lives on, so `e2e` can set or break it. Ids only, never content.
    fix: dict[str, str] | None = None


@dataclass
class KnownGap:
    id: str
    reason: str


@dataclass
class Report:
    course: str
    moodle_source: str
    openlms_source: str
    findings: list[Finding]
    stale_gaps: list[KnownGap] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not any(f.status == FAIL for f in self.findings)

    def count(self, status: str) -> int:
        return sum(1 for f in self.findings if f.status == status)

    def by_id(self, fid: str) -> Finding | None:
        return next((f for f in self.findings if f.id == fid), None)
