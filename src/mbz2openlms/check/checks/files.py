"""Files: every file Moodle content embeds is uploaded, and every /static/ link resolves."""

from __future__ import annotations

import re

from lxml import etree

from ..context import Context
from ..findings import FAIL, PASS

STATIC_REF = re.compile(r"""/static/([^"'\s<>)?#]+)""")


def run(ctx: Context) -> None:
    static = ctx.openlms.static_files
    for ref in ctx.moodle.refs:
        if ref.kind != "pluginfile" or not ref.present or not ref.file:
            continue
        name = ref.file.rsplit("/", 1)[-1]
        # Uploads may be renamed (prefixed, spaces replaced): compare normalised names.
        ok = any(_key(s).endswith(_key(name)) for s in static)
        detail = f"'{name}' " + ("uploaded" if ok else "not in Files & Uploads")
        ctx.add(f"file|{ref.location}|{name}", "files", ref.location, PASS if ok else FAIL, detail)
    refs: set[str] = set()
    for _section, _sub, unit in ctx.openlms.units():
        refs.update(STATIC_REF.findall(etree.tostring(unit.xml, encoding="unicode")))
        refs.update(m for t in unit.xml.itertext() for m in STATIC_REF.findall(t))
    for name in sorted(refs - static):
        detail = f"content links to /static/{name}, which is not uploaded"
        ctx.add(f"static|{name}", "files", "Files & Uploads", FAIL, detail)


def _key(name: str) -> str:
    return re.sub(r"[^a-z0-9.]+", "_", name.rsplit("/", 1)[-1].lower())
