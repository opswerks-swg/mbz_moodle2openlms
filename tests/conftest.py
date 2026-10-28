"""Shared fixtures: the synthetic backup (see ``fixtures/mbz_builder.py``) and its conversion."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from mbz2openlms.convert import Options, convert
from mbz2openlms.moodle.reader import read_course
from mbz2openlms.olx.writer import pack, write
from tests.fixtures.mbz_builder import pack_mbz, sample_backup

SAMPLE_MBZ = os.environ.get("M2O_SAMPLE_MBZ")


@pytest.fixture(scope="session")
def backup_dir(tmp_path_factory) -> Path:
    return sample_backup(tmp_path_factory.mktemp("backup"))


@pytest.fixture(scope="session")
def backup_mbz(backup_dir, tmp_path_factory) -> Path:
    return pack_mbz(backup_dir, tmp_path_factory.mktemp("mbz") / "synthetic.mbz")


@pytest.fixture()
def course(backup_dir):
    return read_course(backup_dir, "synthetic.mbz")


@pytest.fixture(scope="session")
def olx_dir(backup_dir, tmp_path_factory) -> Path:
    """The converted course, written once; copy it before changing it (``olx_copy``)."""
    result = convert(read_course(backup_dir, "synthetic.mbz"), Options())
    return write(result.olx, tmp_path_factory.mktemp("olx"))


@pytest.fixture()
def olx_copy(olx_dir, tmp_path) -> Path:
    return Path(shutil.copytree(olx_dir, tmp_path / "course"))


@pytest.fixture()
def olx_archive(olx_dir, tmp_path) -> Path:
    return pack(olx_dir, tmp_path / "course.tar.gz")


@pytest.fixture(scope="session")
def sample_mbz() -> Path:
    if not SAMPLE_MBZ:
        pytest.skip("set M2O_SAMPLE_MBZ=<course backup .mbz> to run the real-course tests")
    path = Path(SAMPLE_MBZ).expanduser()
    if not path.is_file():
        pytest.fail(f"M2O_SAMPLE_MBZ not found: {path}")
    return path
