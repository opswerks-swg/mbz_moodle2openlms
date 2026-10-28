"""An Open edX course as the converter builds it, before it is written as OLX."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lxml import etree


@dataclass
class Component:
    block_type: str
    url_name: str
    display_name: str
    # "html": the HTML text. Any other type: the block's element.
    content: etree._Element | str
    # Blocks this one points at by url_name (the problems of a problem bank).
    children: list[Component] = field(default_factory=list)
    # Pure XBlocks (ORA, survey) are only read when written inside their unit.
    inline: bool = False


@dataclass
class Unit:
    url_name: str
    display_name: str
    components: list[Component] = field(default_factory=list)


@dataclass
class Subsection:
    url_name: str
    display_name: str
    units: list[Unit] = field(default_factory=list)
    # graded, format (assignment type), start, due, is_time_limited, show_correctness, ...
    attrs: dict[str, str] = field(default_factory=dict)


@dataclass
class Section:
    url_name: str
    display_name: str
    subsections: list[Subsection] = field(default_factory=list)


@dataclass
class Course:
    org: str
    number: str
    run: str
    display_name: str
    start: str | None = None
    sections: list[Section] = field(default_factory=list)
    policy: dict[str, Any] = field(default_factory=dict)
    grading_policy: dict[str, Any] = field(default_factory=dict)
    static: dict[str, Path] = field(default_factory=dict)  # name under /static/ -> source
    _names: set[str] = field(default_factory=set)

    def url_name(self, *parts: object) -> str:
        """A unique, readable url_name built from ``parts``."""
        base = re.sub(r"[^A-Za-z0-9_.-]+", "_", "_".join(str(p) for p in parts)).strip("_")
        name, n = base or "block", 2
        while name in self._names:
            name, n = f"{base}_{n}", n + 1
        self._names.add(name)
        return name

    def components(self) -> list[Component]:
        def walk(items: list[Component]):
            for c in items:
                yield c
                yield from walk(c.children)

        return [
            c
            for s in self.sections
            for sub in s.subsections
            for u in sub.units
            for c in walk(u.components)
        ]
