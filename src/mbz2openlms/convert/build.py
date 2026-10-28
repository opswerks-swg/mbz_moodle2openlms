"""State shared by the converter's handlers while one course is converted.

``Build`` holds the OLX course being built, the notes for the conversion report (manual
follow-ups, dropped features), the static files to copy, and what the grading policy needs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import unquote

from .. import credentials
from ..htmlutil import links, plain_text
from ..moodle.model import Activity, Course, File
from ..olx.model import Component, Subsection, Unit
from ..olx.model import Course as OlxCourse
from .xhtml import rewrite_links

# Note kinds, in the order the report lists them.
MANUAL, DROPPED, INFO = "manual", "dropped", "info"


@dataclass
class Options:
    org: str = "OpsWerks"
    number: str | None = None
    run: str = "2026"
    # Keep quiz time limits (only once timed exams are enabled on OpenLMS).
    timed_exams: bool = False
    # Keep Moodle's open/close/due dates. Off by default: they belong to the old run, and
    # imported past dates would close quizzes and show their answers straight away.
    keep_dates: bool = False


@dataclass(frozen=True)
class Note:
    kind: str
    where: str
    detail: str


@dataclass
class Units:
    """What a handler returns: the units of one activity and its subsection settings."""

    units: list[Unit]
    attrs: dict[str, str] = field(default_factory=dict)


@dataclass
class Build:
    course: Course
    opts: Options
    olx: OlxCourse
    notes: list[Note] = field(default_factory=list)
    # Grading: assignment type -> share of the course grade (None = unknown).
    weights: dict[str, float | None] = field(default_factory=dict)
    fixed_weights: dict[str, float] = field(default_factory=dict)
    pass_ratios: list[float] = field(default_factory=list)
    gating: bool = False
    # Moodle dates of the old run, for the report: (where, what, when).
    dates: list[tuple[str, str, datetime]] = field(default_factory=list)
    # Activity cmid -> name of the subsection it was placed in.
    placed_in: dict[int, str] = field(default_factory=dict)
    placements: list[tuple[str, str]] = field(default_factory=list)

    def note(self, kind: str, where: str, detail: str) -> None:
        note = Note(kind, where, detail)
        if note not in self.notes:
            self.notes.append(note)

    def unit(self, key: object, name: str, components: list[Component]) -> Unit:
        return Unit(self.olx.url_name("unit", key), name, components)

    def html(self, name: str, html: str, context_id: int | None, where: str) -> Component:
        return Component(
            "html",
            self.olx.url_name("html", _slug(name)),
            name,
            self.rewrite(html, context_id, where),
        )

    def rewrite(self, html: str, context_id: int | None, where: str) -> str:
        """Fix file links and Moodle links in ``html`` and note what needs a manual fix."""

        def static_name(path: str) -> str | None:
            name = unquote(path).split("?", 1)[0]
            f = self.course.file(context_id, name)
            if f is None or not f.present:
                self.note(
                    MANUAL,
                    where,
                    f"Embedded file '{name.rsplit('/', 1)[-1]}' is not in the backup: upload it "
                    "in Files & Uploads and fix the link.",
                )
                return None
            return self.static(f)

        def moodle_link(link: str) -> None:
            self.note(MANUAL, where, f"Link to another Moodle item ({link}) removed: re-link it.")

        out = rewrite_links(html or "", static_name, moodle_link)
        for link in links(out):
            if link.kind == "relative" and not link.url.startswith(("/static/", "/jump_to")):
                self.note(
                    MANUAL,
                    where,
                    f"Relative link '{link.url[:60]}' won't resolve on OpenLMS: fix or remove it.",
                )
        for kind, shown in credentials.find(plain_text(out)):
            self.note(
                MANUAL,
                where,
                f"Possible {kind} ('{shown}'): remove it or replace it with a placeholder in "
                "Studio. The checker fails until it is gone.",
            )
        return out

    def static(self, f: File) -> str:
        name = f"{f.context_id}_{re.sub(r'[^A-Za-z0-9._-]+', '_', f.filename)}"
        self.olx.static[name] = f.path
        return name

    def record_date(self, where: str, what: str, when: datetime | None) -> None:
        if when and (where, what, when) not in self.dates:
            self.dates.append((where, what, when))

    def date_attr(self, attrs: dict[str, str], key: str, when: datetime | None) -> None:
        if when and self.opts.keep_dates:
            attrs[key] = olx_date(when)

    def graded(self, act: Activity, assignment_type: str) -> dict[str, str]:
        """Subsection attributes for a graded activity, recording its weight and pass mark."""
        self.weights[assignment_type] = self.course.gradebook.weights().get(act.cmid)
        item = self.course.gradebook.item(act.cmid)
        if item and item.grade_max and item.grade_pass:
            self.pass_ratios.append(item.grade_pass / item.grade_max)
        return {"graded": "true", "format": assignment_type}

    def place(self, acts: list[Activity], section: str, subsection: Subsection) -> None:
        for act in acts:
            self.placed_in[act.cmid] = subsection.display_name
            self.placements.append((act.where, f"{section} › {subsection.display_name}"))


def olx_date(when: datetime) -> str:
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def _slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")[:60] or "item"
