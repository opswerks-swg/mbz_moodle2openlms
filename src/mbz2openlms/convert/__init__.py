"""Convert a Moodle course into an Open edX course (OLX).

Anything that can't be carried over is recorded as a ``Note`` and listed in the conversion
report, so the instructor knows exactly what to finish by hand in Studio.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from ..moodle.model import Course
from ..olx.model import Course as OlxCourse
from .build import DROPPED, INFO, MANUAL, Build, Note, Options, olx_date
from .grading import build_policies
from .structure import build_sections

__all__ = ["DROPPED", "INFO", "MANUAL", "Note", "Options", "Result", "convert"]


@dataclass
class Result:
    olx: OlxCourse
    notes: list[Note]
    placements: list[tuple[str, str]]
    dates: list[tuple[str, str, datetime]]
    options: Options

    @property
    def stats(self) -> dict[str, int]:
        subs = [s for c in self.olx.sections for s in c.subsections]
        units = [u for s in subs for u in s.units]
        counts = Counter(c.block_type for c in self.olx.components())
        return {
            "sections": len(self.olx.sections),
            "subsections": len(subs),
            "units": len(units),
            "static files": len(self.olx.static),
            **dict(counts),
        }


def convert(course: Course, opts: Options | None = None) -> Result:
    opts = opts or Options()
    number = opts.number or re.sub(r"[^A-Za-z0-9_.-]+", "_", course.shortname or "COURSE").upper()
    olx = OlxCourse(
        org=opts.org,
        number=number,
        run=opts.run,
        display_name=course.fullname,
        start=olx_date(course.start) if course.start and opts.keep_dates else None,
    )
    b = Build(course, opts, olx)
    build_sections(b)
    build_policies(b)
    return Result(olx, b.notes, b.placements, b.dates, opts)
