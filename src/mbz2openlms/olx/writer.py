"""Write a ``Course`` as OLX (the layout Studio exports and imports) and pack it.

course/course.xml                       pointer: org, number, run
course/course/<run>.xml                 course root, lists the chapters
course/chapter|sequential|vertical/…    sections, subsections, units
course/<block type>/<url_name>.xml      components (html also has <url_name>.html)
course/static/                          files referenced as /static/<name>
course/policies/<run>/policy.json, grading_policy.json
"""

from __future__ import annotations

import json
import tarfile
from copy import deepcopy
from pathlib import Path
from typing import Any

from lxml import etree

from .model import Component, Course


def write(course: Course, dest: Path) -> Path:
    """Write ``dest/course/`` and return it."""
    root = dest / "course"
    if root.exists():
        raise FileExistsError(root)

    def save(rel: str, data: str | bytes) -> None:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, bytes):
            path.write_bytes(data)
        else:
            path.write_text(data, encoding="utf-8")

    pointer = etree.Element("course", url_name=course.run, org=course.org, course=course.number)
    save("course.xml", _xml(pointer))
    course_el = etree.Element("course", display_name=course.display_name)
    if course.start:
        course_el.set("start", course.start)
    for section in course.sections:
        etree.SubElement(course_el, "chapter", url_name=section.url_name)
        chapter = etree.Element("chapter", display_name=section.display_name)
        for sub in section.subsections:
            etree.SubElement(chapter, "sequential", url_name=sub.url_name)
            seq = etree.Element("sequential", display_name=sub.display_name, **sub.attrs)
            for unit in sub.units:
                etree.SubElement(seq, "vertical", url_name=unit.url_name)
                vert = etree.Element("vertical", display_name=unit.display_name)
                for comp in unit.components:
                    if comp.inline:
                        el = deepcopy(comp.content)
                        el.set("url_name", comp.url_name)
                        el.set("display_name", comp.display_name)
                        vert.append(el)
                    else:
                        etree.SubElement(vert, comp.block_type, url_name=comp.url_name)
                        _save_component(comp, save)
                save(f"vertical/{unit.url_name}.xml", _xml(vert))
            save(f"sequential/{sub.url_name}.xml", _xml(seq))
        save(f"chapter/{section.url_name}.xml", _xml(chapter))
    save(f"course/{course.run}.xml", _xml(course_el))
    save(f"policies/{course.run}/policy.json", _json({f"course/{course.run}": course.policy}))
    save(f"policies/{course.run}/grading_policy.json", _json(course.grading_policy))
    save("policies/assets.json", "{}\n")
    for name, source in course.static.items():
        save(f"static/{name}", source.read_bytes())
    return root


def _save_component(comp: Component, save) -> None:
    if comp.block_type == "html":
        el = etree.Element("html", filename=comp.url_name, display_name=comp.display_name)
        save(f"html/{comp.url_name}.xml", _xml(el))
        save(f"html/{comp.url_name}.html", comp.content)
        return
    save(f"{comp.block_type}/{comp.url_name}.xml", _xml(comp.content))
    for child in comp.children:
        _save_component(child, save)


def pack(course_dir: Path, archive: Path) -> Path:
    """The .tar.gz Studio imports: one top-level ``course/`` folder."""
    with tarfile.open(archive, "w:gz") as tf:
        tf.add(course_dir, arcname="course")
    return archive


def _xml(el: etree._Element) -> str:
    return etree.tostring(el, encoding="unicode", pretty_print=True)


def _json(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"
