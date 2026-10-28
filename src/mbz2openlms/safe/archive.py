"""Open untrusted archives: Moodle backups (.mbz) and Studio exports (.tar.gz).

Members that would land outside the destination (absolute paths, ``..``, links, devices) are
rejected. A ``.mbz`` is a gzipped tar, or a zip from older Moodle sites.
"""

from __future__ import annotations

import contextlib
import tarfile
import tempfile
import zipfile
from collections.abc import Iterator
from pathlib import Path


class ArchiveError(Exception):
    pass


def extract(archive: Path, dest: Path) -> Path:
    """Extract ``archive`` into the empty directory ``dest`` and return ``dest``."""
    dest.mkdir(parents=True, exist_ok=True)
    if any(dest.iterdir()):
        raise ArchiveError(f"Extraction directory is not empty: {dest}")
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as zf:
            root = dest.resolve()
            for name in zf.namelist():
                if not (dest / name).resolve().is_relative_to(root):
                    raise ArchiveError(f"Unsafe path in {archive.name}: {name}")
            zf.extractall(dest)
    elif tarfile.is_tarfile(archive):
        with tarfile.open(archive, "r:*") as tf:
            try:
                tf.extractall(dest, filter="data")
            except tarfile.FilterError as exc:
                raise ArchiveError(f"Unsafe path in {archive.name}: {exc}") from exc
    else:
        raise ArchiveError(f"Not a tar or zip archive: {archive}")
    return dest


@contextlib.contextmanager
def opened(source: Path, marker: str, what: str) -> Iterator[Path]:
    """Yield a directory with the archive's contents, found by the file ``marker``.

    ``source`` may be an archive (extracted to a temporary directory removed afterwards) or a
    directory that is already extracted. The yielded directory is the one holding ``marker``,
    which may sit one level down (a Studio export wraps everything in ``course/``).
    """
    if source.is_dir():
        yield _root(source, marker, what)
        return
    if not source.is_file():
        raise ArchiveError(f"{what} not found: {source}")
    with tempfile.TemporaryDirectory(prefix="mbz2openlms-") as tmp:
        yield _root(extract(source, Path(tmp) / "x"), marker, what)


def _root(folder: Path, marker: str, what: str) -> Path:
    if (folder / marker).is_file():
        return folder
    found = sorted(p.parent for p in folder.glob(f"*/{marker}"))
    if not found:
        raise ArchiveError(f"{marker} not found in {folder.name}: is this a {what}?")
    return found[0]
