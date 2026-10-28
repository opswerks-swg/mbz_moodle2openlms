"""Local tutor dev only (``docker exec``): create test courses, the checker's OAuth client and
its Staff role, and export a course with Studio's own export function. Never preprod or prod.
"""

from __future__ import annotations

import secrets
import subprocess
from pathlib import Path

CREATE_COURSE = """
from cms.djangoapps.contentstore.views.course import create_new_course
from django.contrib.auth import get_user_model
from opaque_keys.edx.keys import CourseKey
from xmodule.modulestore.django import modulestore
for k in {keys!r}:
    key = CourseKey.from_string(k)
    if modulestore().get_course(key) is None:
        admin = get_user_model().objects.filter(is_superuser=True, is_active=True).first()
        create_new_course(admin, key.org, key.course, key.run, {{"display_name": "m2o e2e"}})
        print("M2O created", k)
    else:
        print("M2O exists", k)
"""

GRANT_STAFF = """
from django.contrib.auth import get_user_model
from common.djangoapps.student.roles import CourseStaffRole
from opaque_keys.edx.keys import CourseKey
user = get_user_model().objects.get(username={user!r})
for k in {keys!r}:
    CourseStaffRole(CourseKey.from_string(k)).add_users(user)
    print("M2O staff", k)
"""

EXPORT = """
import shutil
from cms.djangoapps.contentstore.tasks import create_export_tarball
from opaque_keys.edx.keys import CourseKey
from xmodule.modulestore.django import modulestore
key = CourseKey.from_string({key!r})
tarball = create_export_tarball(modulestore().get_course(key), key, {{}})
shutil.copy(tarball.name, "/tmp/m2o-e2e-export.tar.gz")
print("M2O exported")
"""

SERVICE_USER = "m2o_checker"
CLIENT_ID = "m2o-checker-local"


def setup(course_keys: list[str], lms: str, cms: str, create: bool, log=print) -> tuple[str, str]:
    """Return (client id, a new client secret). The secret is rotated on every call."""
    if create:
        for line in _shell(cms, "cms", CREATE_COURSE.format(keys=course_keys)):
            log(f"   {line}")
    secret = secrets.token_hex(24)
    _manage(lms, "manage_user", SERVICE_USER, f"{SERVICE_USER}@example.com")
    app = ["create_dot_application", "m2o-checker-local", SERVICE_USER]
    app += ["--grant-type", "client-credentials", "--client-id", CLIENT_ID]
    app += ["--client-secret", secret]
    try:
        _manage(lms, *app, "--update")
    except subprocess.CalledProcessError:
        _manage(lms, *app)  # first run: nothing to update yet
    for line in _shell(lms, "lms", GRANT_STAFF.format(user=SERVICE_USER, keys=course_keys)):
        log(f"   {line}")
    return CLIENT_ID, secret


def export(container: str, course_key: str, dest: Path) -> Path:
    """Export a course with Studio's own export (there is no token API for it)."""
    _shell(container, "cms", EXPORT.format(key=course_key))
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["docker", "cp", f"{container}:/tmp/m2o-e2e-export.tar.gz", str(dest)]
    subprocess.run(cmd, check=True, capture_output=True)
    return dest


def _manage(container: str, *args: str) -> None:
    cmd = ["docker", "exec", "-w", "/openedx/edx-platform", container, "./manage.py", "lms"]
    subprocess.run(cmd + list(args), check=True, capture_output=True)


def _shell(container: str, service: str, script: str) -> list[str]:
    done = subprocess.run(
        ["docker", "exec", "-i", "-w", "/openedx/edx-platform", container]
        + ["./manage.py", service, "shell"],
        input=script,
        text=True,
        check=True,
        capture_output=True,
    )
    lines = [line[4:] for line in done.stdout.splitlines() if line.startswith("M2O ")]
    if not lines:
        raise subprocess.CalledProcessError(1, "manage.py shell", done.stdout, done.stderr[-500:])
    return lines
