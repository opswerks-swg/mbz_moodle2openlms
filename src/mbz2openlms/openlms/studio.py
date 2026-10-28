"""Read a migrated course through the Studio REST APIs, and change it (for ``e2e``).

Needs an OAuth client (client-credentials grant, JWT) whose service user has the Studio Staff
role on the course:

* ``/api/contentstore/v1/course_index/<course>``: outline, prerequisites, dates, grading types
* ``/api/contentstore/v1/course_grading/<course>``: grading policy and cutoffs
* ``/api/olx-export/v1/xblock/<unit>/``: each unit's OLX with its components inline
"""

from __future__ import annotations

import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from lxml import etree

from ..safe.xml import parse_olx
from .model import MigratedCourse, MigratedError, Section, Subsection, Unit

# olx-export (Ulmo) rewrites /static/<name> links as served asset URLs, e.g.
# /assets/courseware/v1/<hash>/asset-v1:Org+Course+Run+type@asset+block/<name>
ASSET_URL = re.compile(
    r"""(?:https?://[^/"'\s]+)?(/assets/courseware/v1/[0-9a-f]+/asset-v1:[^/"'\s<>]+"""
    r"""\+type@asset\+block[/@]([^"'\s<>?#]+))"""
)
HINTS = {
    401: "not authorised (expired or rejected token)",
    403: "forbidden: the client's service user needs the Studio Staff role on the course",
    404: "not found: check the course key and the Studio URL",
}


class StudioClient:
    def __init__(
        self,
        studio_url: str,
        lms_url: str,
        client_id: str,
        client_secret: str,
        ca_bundle: Path | None = None,
        timeout: float = 60,
    ) -> None:
        self.studio = studio_url.rstrip("/")
        self.lms = lms_url.rstrip("/")
        self.timeout = timeout
        self.ssl = ssl.create_default_context(cafile=str(ca_bundle) if ca_bundle else None)
        body = urllib.parse.urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "token_type": "jwt",
            }
        ).encode()
        what = "OAuth token (check the client id and secret)"
        self._token = self._request(f"{self.lms}/oauth2/access_token", body, what=what)[
            "access_token"
        ]

    def get(self, path: str) -> Any:
        return self._request(f"{self.studio}{path}", auth=True)

    def get_xblock(self, course_key: str, usage_key: str) -> Any:
        return self.get(f"/api/contentstore/v0/xblock/{course_key}/{usage_key}")

    def patch_xblock(self, course_key: str, usage_key: str, payload: dict[str, Any]) -> Any:
        """Change a block as Studio's editor does (fields, metadata, prerequisites, publish)."""
        return self._request(
            f"{self.studio}/api/contentstore/v0/xblock/{course_key}/{usage_key}",
            json.dumps(payload).encode(),
            auth=True,
            method="PATCH",
            ctype="application/json",
        )

    def import_course(self, course_key: str, archive: Path) -> str:
        """Start a Studio import into an existing course. It replaces the content."""
        boundary = uuid.uuid4().hex
        body = b"".join(
            [
                f'--{boundary}\r\nContent-Disposition: form-data; name="course_data"; '
                f'filename="{archive.name}"\r\nContent-Type: application/gzip\r\n\r\n'.encode(),
                archive.read_bytes(),
                f"\r\n--{boundary}--\r\n".encode(),
            ]
        )
        data = self._request(
            f"{self.studio}/api/courses/v0/import/{course_key}/",
            body,
            auth=True,
            what="import (the course must exist in Studio first)",
            ctype=f"multipart/form-data; boundary={boundary}",
        )
        return data["task_id"]

    def import_state(self, course_key: str, task_id: str, filename: str) -> str:
        query = urllib.parse.urlencode({"task_id": task_id, "filename": filename})
        return self.get(f"/api/courses/v0/import/{course_key}/?{query}")["state"]

    def exists(self, url: str) -> bool:
        """True if a static file URL is served."""
        try:
            request = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(request, context=self.ssl, timeout=self.timeout):
                return True
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return False
            raise MigratedError(f"{url}: HTTP {exc.code}") from exc

    def _request(
        self,
        url: str,
        data: bytes | None = None,
        auth: bool = False,
        what: str = "",
        method: str | None = None,
        ctype: str | None = None,
    ) -> Any:
        headers = {"Accept": "application/json"}
        if auth:
            headers["Authorization"] = f"JWT {self._token}"
        if ctype:
            headers["Content-Type"] = ctype
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, context=self.ssl, timeout=self.timeout) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            hint = HINTS.get(exc.code, "")
            raise MigratedError(f"{what or url}: HTTP {exc.code} {hint}".rstrip()) from exc
        except urllib.error.URLError as exc:
            hint = ""
            if isinstance(exc.reason, ssl.SSLCertVerificationError):
                hint = " (for a local tutor, pass --ca-bundle with Caddy's local root.crt)"
            raise MigratedError(f"{what or url}: {exc.reason}{hint}") from exc


def from_studio(client: StudioClient, course_key: str) -> MigratedCourse:
    quoted = urllib.parse.quote(course_key, safe=":+")
    index = client.get(f"/api/contentstore/v1/course_index/{quoted}")
    details = client.get(f"/api/contentstore/v1/course_grading/{quoted}")["course_details"]
    sections = []
    static_urls: dict[str, str] = {}
    block_ids: dict[etree._Element, str] = {}
    for ch in _children(index["course_structure"]):
        section = Section(ch["id"], ch.get("display_name") or "")
        for seq in _children(ch):
            sub = Subsection(
                id=seq["id"],
                name=seq.get("display_name") or "",
                graded=bool(seq.get("graded")),
                format=seq.get("format"),
                start=seq.get("start"),
                due=seq.get("due"),
                time_limited=bool(seq.get("is_time_limited")),
                prereq=seq.get("prereq") or None,
                prereq_min_score=_float(seq.get("prereq_min_score")),
            )
            for vert in _children(seq):
                olx = client.get(f"/api/olx-export/v1/xblock/{urllib.parse.quote(vert['id'])}/")
                text = olx["blocks"][vert["id"]]["olx"]
                for path, name in ASSET_URL.findall(text):
                    static_urls[urllib.parse.unquote(name)] = client.studio + path
                xml = parse_olx(_static_links(text).encode("utf-8"))
                unit = Unit(
                    vert["id"],
                    vert.get("display_name") or "",
                    xml,
                    published=bool(vert.get("published")),
                    has_changes=bool(vert.get("has_changes")),
                )
                sub.units.append(unit)
                block_ids.update(_block_ids(xml, list(olx["blocks"])))
                for block in olx["blocks"].values():
                    for name, info in (block.get("static_files") or {}).items():
                        if info.get("url"):
                            static_urls[name] = info["url"]
            section.subsections.append(sub)
        sections.append(section)
    graders = {g["type"]: float(g["weight"]) / 100 for g in details.get("graders", [])}
    cutoff = (details.get("grade_cutoffs") or {}).get("Pass")
    # olx-export lists every /static/ reference, whether the file exists or not.
    missing = {name for name, url in static_urls.items() if not client.exists(url)}
    return MigratedCourse(
        source=f"Studio API {client.studio}",
        course_key=course_key,
        sections=sections,
        graders=graders,
        cutoff=cutoff,
        prereqs_known=True,
        static_files=set(static_urls) - missing,
        block_ids=block_ids,
    )


def _static_links(olx: str) -> str:
    """Asset URLs back to /static/<name>, as in an export, so both sources read the same."""
    return ASSET_URL.sub(lambda m: f"/static/{urllib.parse.unquote(m.group(2))}", olx)


def _block_ids(unit: etree._Element, keys: list[str]) -> dict[etree._Element, str]:
    """Pair the unit's inline components with their usage keys.

    olx-export lists keys in document order, but the inline OLX has no url_name: pair them per
    block type, and only when the counts agree.
    """
    by_type: dict[str, list[str]] = {}
    for key in keys:
        by_type.setdefault(key.split("+type@", 1)[1].split("+", 1)[0], []).append(key)
    found = {}
    for block_type, type_keys in by_type.items():
        elements = [unit] if block_type == unit.tag else list(unit.iter(block_type))
        if len(elements) == len(type_keys):
            found.update(zip(elements, type_keys, strict=True))
    return found


def _children(block: dict[str, Any]) -> list[dict[str, Any]]:
    return (block.get("child_info") or {}).get("children") or []


def _float(value: Any) -> float | None:
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None
