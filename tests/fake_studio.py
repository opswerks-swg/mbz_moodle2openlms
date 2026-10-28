"""A fake Studio + LMS serving a converted course through the APIs the checker reads.

Built from an OLX course folder: ``course_index`` (outline, prerequisites, dates),
``course_grading``, ``olx-export`` per unit, static files, the OAuth token, and the
``xblock`` PATCH / import endpoints ``e2e`` uses.
"""

from __future__ import annotations

import json
import re
import threading
import urllib.parse
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from lxml import etree

from mbz2openlms.openlms.export import read_olx

KEY = "course-v1:OpsWerks+SYN+2026"


def usage(block_type: str, name: str) -> str:
    return f"block-v1:OpsWerks+SYN+2026+type@{block_type}+block@{name}"


@dataclass
class FakeStudio:
    root: Path
    prereqs: dict[str, tuple[str, float]] = field(default_factory=dict)  # sub id -> (id, score)
    unpublished: set[str] = field(default_factory=set)  # unit ids
    patches: list[tuple[str, dict]] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    is_prereq: set[str] = field(default_factory=set)  # sub ids
    changed: set[str] = field(default_factory=set)  # unit ids with unpublished changes

    def __post_init__(self) -> None:
        self.course = read_olx(self.root, "fake")

    def index(self) -> dict:
        def child(kind, name, children, **extra):
            return {"id": usage(kind, name), "display_name": name, **extra,
                    "child_info": {"children": children}}  # fmt: skip

        sections = []
        for s in self.course.sections:
            subs = []
            for sub in s.subsections:
                units = [
                    {
                        "id": usage("vertical", u.id),
                        "display_name": u.name,
                        "published": u.id not in self.unpublished,
                        "has_changes": u.id in self.changed,
                    }
                    for u in sub.units
                ]
                prereq, score = self.prereqs.get(sub.id, (None, None))
                subs.append(
                    child(
                        "sequential", sub.id, units,
                        display_name=sub.name, graded=sub.graded, format=sub.format,
                        due=sub.due, start=sub.start,
                        prereq=usage("sequential", prereq) if prereq else "",
                        prereq_min_score=score,
                        is_prereq=sub.id in self.is_prereq,
                    )
                )  # fmt: skip
            sections.append(child("chapter", s.id, subs, display_name=s.name))
        return {"course_structure": {"child_info": {"children": sections}}}

    def grading(self) -> dict:
        policy = json.loads((self.root / "policies/2026/grading_policy.json").read_text())
        graders = [{"type": g["type"], "weight": g["weight"] * 100} for g in policy["GRADER"]]
        return {"course_details": {"graders": graders, "grade_cutoffs": policy["GRADE_CUTOFFS"]}}

    def unit_olx(self, unit_key: str) -> dict:
        for _s, _sub, unit in self.course.units():
            if usage("vertical", unit.id) != unit_key:
                continue
            xml = etree.tostring(unit.xml, encoding="unicode")
            # Like Ulmo: /static/ links come back as served asset URLs.
            xml = re.sub(
                r"/static/([^\"'\s<>)?#&]+)",
                lambda m: (
                    f"/assets/courseware/v1/0123abcd/asset-v1:OpsWerks+SYN+2026"
                    f"+type@asset+block/{m.group(1)}"
                ),
                xml,
            )
            blocks = {unit_key: {"olx": xml}}
            for el in unit.xml.iter():
                if isinstance(el.tag, str) and el is not unit.xml and el.get("url_name"):
                    blocks[usage(el.tag, el.get("url_name"))] = {}
            return {"blocks": blocks}
        raise KeyError(unit_key)

    def find(self, key: str):
        """(unit, element) for a component usage key, or (None, subsection) for a sequential."""
        block_type, name = key.split("+type@", 1)[1].split("+block@")
        if block_type == "sequential":
            return None, next(sub for _, sub in self.course.subsections() if sub.id == name)
        for _s, _sub, unit in self.course.units():
            for el in unit.xml.iter(block_type):
                if el.get("url_name") == name:
                    return unit, el
        raise KeyError(key)

    def patch(self, key: str, payload: dict) -> None:
        unit, target = self.find(key)
        if unit is None:  # a subsection
            if "isPrereq" in payload:
                (self.is_prereq.add if payload["isPrereq"] else self.is_prereq.discard)(target.id)
                if not payload["isPrereq"]:
                    self.prereqs = {k: v for k, v in self.prereqs.items() if v[0] != target.id}
            if "prereqUsageKey" in payload:
                prereq = payload["prereqUsageKey"].split("+block@")[1]
                self.prereqs[target.id] = (prereq, float(payload["prereqMinScore"]))
            if "metadata" in payload:
                target.due = payload["metadata"].get("due", target.due)
            return
        if "data" in payload and target.tag == "html":  # an HTML component's data is its HTML
            target.text = payload["data"]
            self.changed.add(unit.id)
        elif "data" in payload:
            new = etree.fromstring(payload["data"].encode())
            for name in ("url_name", "display_name"):
                if target.get(name) and not new.get(name):
                    new.set(name, target.get(name))
            target.getparent().replace(target, new)
            self.changed.add(unit.id)
        for name, value in (payload.get("metadata") or {}).items():
            target.set(name, value)
        if payload.get("publish") == "make_public":
            self.changed.discard(unit.id)

    def serve(self):
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):  # quiet
                pass

            def _send(self, code: int, data=None):
                body = json.dumps(data).encode() if data is not None else b""
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(body)

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                self.rfile.read(length)
                if self.path == "/oauth2/access_token":
                    return self._send(200, {"access_token": "token"})
                if self.path.startswith("/api/courses/v0/import/"):
                    fake.imports.append(self.path)
                    return self._send(200, {"task_id": "t1"})
                return self._send(404)

            def do_PATCH(self):
                length = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(length))
                fake.patches.append((self.path, payload))
                fake.patch(urllib.parse.unquote(self.path).rsplit("/", 1)[1], payload)
                return self._send(200, {})

            def do_HEAD(self):
                name = self.path.rsplit("+type@asset+block/", 1)[-1]
                ok = (fake.root / "static" / urllib.parse.unquote(name)).is_file()
                return self._send(200 if ok else 404)

            def do_GET(self):
                path = urllib.parse.unquote(self.path)
                if self.headers.get("Authorization") != "JWT token":
                    return self._send(401)
                if path == f"/api/contentstore/v1/course_index/{KEY}":
                    return self._send(200, fake.index())
                if path == f"/api/contentstore/v1/course_grading/{KEY}":
                    return self._send(200, fake.grading())
                if path.startswith("/api/courses/v0/import/"):
                    return self._send(200, {"state": "Succeeded"})
                if path.startswith("/api/contentstore/v0/xblock/"):
                    _unit, el = fake.find(path.rsplit("/", 1)[1])
                    data = (
                        el.text or ""
                        if el.tag == "html"
                        else etree.tostring(el, encoding="unicode")
                    )
                    return self._send(200, {"data": data})
                if path.startswith("/api/olx-export/v1/xblock/"):
                    key = path.removeprefix("/api/olx-export/v1/xblock/").rstrip("/")
                    return self._send(200, fake.unit_olx(key))
                return self._send(404)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return server
