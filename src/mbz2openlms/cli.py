"""Command line: ``mbz2openlms inventory | convert | check | gaps init | e2e``.

Exit status: 0 success (``check``: PASS), 1 ``check`` FAIL, 2 usage or input error.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import click

from . import __version__
from .check import Rules, known_gaps, predict_gaps
from .check import check as run_check
from .convert import Options
from .convert import convert as run_convert
from .e2e import local as e2e_local
from .e2e.run import E2E, default_due
from .moodle.reader import open_backup, read_backup, read_course
from .olx.writer import pack, write
from .openlms.export import from_export
from .openlms.model import MigratedError
from .openlms.studio import StudioClient, from_studio
from .report import check as check_report
from .report import conversion, to_json
from .report import inventory as inventory_report
from .safe.archive import ArchiveError

OUT = Path("out")
BACKUP = click.Path(exists=True, path_type=Path)


class Failed(click.ClickException):
    exit_code = 2


def main(argv: list[str] | None = None) -> int:
    try:
        return cli.main(args=argv, standalone_mode=False) or 0
    except click.exceptions.Exit as exc:
        return exc.exit_code
    except click.ClickException as exc:
        exc.show()
        return 2
    except click.exceptions.Abort:
        click.echo("Aborted.", err=True)
        return 2


@click.group()
@click.version_option(__version__)
def cli() -> None:
    """Migrate a Moodle course backup (.mbz) to OpenLMS, and check the migrated course."""


@cli.command()
@click.argument("backup", type=BACKUP)
@click.option("-o", "--output", type=click.Path(path_type=Path), help="Output folder.")
def inventory(backup: Path, output: Path | None) -> int:
    """Write inventory.md (shareable) and inventory.json (internal: has answer keys)."""

    course = _read(read_backup, backup)
    folder = output or OUT / course.slug
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "inventory.md").write_text(inventory_report.render(course), encoding="utf-8")
    (folder / "inventory.json").write_text(to_json(course), encoding="utf-8")
    click.echo(f"Wrote {folder / 'inventory.md'} and inventory.json (internal: answer keys)")
    return 0


@cli.command()
@click.argument("backup", type=BACKUP)
@click.option("--org", default="OpsWerks", show_default=True)
@click.option("--number", help="Course number. Default: the Moodle short name.")
@click.option("--run", "run_", default="2026", show_default=True)
@click.option("--keep-dates", is_flag=True, help="Keep Moodle's open/close/due dates.")
@click.option("--timed-exams", is_flag=True, help="Keep quiz time limits (needs timed exams).")
@click.option("-o", "--output", type=click.Path(path_type=Path), help="Output folder.")
def convert(backup, org, number, run_, keep_dates, timed_exams, output) -> int:
    """Convert BACKUP into a course archive to import in Studio."""

    opts = Options(org, number, run_, timed_exams, keep_dates)
    archive, folder, result = build_archive(backup, opts, output)
    manual = sum(1 for n in result.notes if n.kind == "manual")
    click.echo(f"Wrote {archive}")
    click.echo(f"Wrote {folder / 'conversion-report.md'}: {manual} manual follow-up(s) in Studio")
    return 0


def build_archive(backup: Path, opts, output: Path | None):
    """Convert and write ``<folder>/<number>-<run>.tar.gz`` plus the reports."""

    try:
        with open_backup(backup) as root:
            course = read_course(root, backup.name)
            result = run_convert(course, opts)
            folder = output or OUT / course.slug
            folder.mkdir(parents=True, exist_ok=True)
            olx = folder / "olx"
            if olx.exists():
                shutil.rmtree(olx)
            course_dir = write(result.olx, olx)
    except ArchiveError as exc:
        raise Failed(str(exc)) from exc
    archive = folder / f"{result.olx.number.lower()}-{result.olx.run}.tar.gz"
    pack(course_dir, archive)
    (folder / "inventory.md").write_text(inventory_report.render(course), encoding="utf-8")
    (folder / "inventory.json").write_text(to_json(course), encoding="utf-8")
    report = conversion.render(course, result, archive.name)
    (folder / "conversion-report.md").write_text(report, encoding="utf-8")
    return archive, folder, result


@cli.command()
@click.argument("backup", type=BACKUP)
@click.option(
    "--export",
    "export",
    type=click.Path(exists=True, path_type=Path),
    help="Studio export (.tar.gz) of the migrated course. No credentials needed.",
)
@click.option("--course", "course_key", help="Course key, read through the Studio APIs.")
@click.option("--studio", envvar="M2O_STUDIO_URL", help="Studio URL [M2O_STUDIO_URL].")
@click.option("--lms", envvar="M2O_LMS_URL", help="LMS URL [M2O_LMS_URL].")
@click.option("--ca-bundle", envvar="M2O_CA_BUNDLE", type=click.Path(exists=True, path_type=Path))
@click.option("--known-gaps", "gaps_path", type=click.Path(exists=True, path_type=Path))
@click.option("--rules", type=click.Path(exists=True, path_type=Path), help="Review rules TOML.")
@click.option("-o", "--output", type=click.Path(path_type=Path), help="Output folder.")
def check(backup, export, course_key, studio, lms, ca_bundle, gaps_path, rules, output) -> int:
    """Compare the migrated course in OpenLMS with BACKUP.

    Exit 0 on PASS, 1 on FAIL. Writes check-report.md (shareable) and check.json.
    """

    if bool(export) == bool(course_key):
        raise click.UsageError("Give exactly one of --export or --course.")
    course = _read(read_backup, backup)
    try:
        if export:
            migrated = from_export(export)
        else:
            migrated = from_studio(client(studio, lms, ca_bundle), course_key)
    except MigratedError as exc:
        raise Failed(str(exc)) from exc
    gaps_file = gaps_path or known_gaps.default_path(course)
    listed = known_gaps.load(gaps_file) if gaps_file.is_file() else []
    report = run_check(course, migrated, listed, Rules.load(rules))
    folder = output or OUT / course.slug
    md = check_report.write(report, folder, gaps_file=gaps_file if gaps_file.is_file() else None)
    click.echo(
        f"{'PASS' if report.passed else 'FAIL'}: "
        + ", ".join(f"{report.count(s)} {s}" for s in ("fail", "warn", "known gap", "not checked"))
        + f", {report.count('pass')} pass"
    )
    if report.stale_gaps:
        click.echo(f"{len(report.stale_gaps)} stale known-gap entr(y/ies): see the report")
    click.echo(f"Wrote {md}")
    return 0 if report.passed else 1


@cli.group()
def gaps() -> None:
    """Known gaps: accepted differences between Moodle and OpenLMS."""


@gaps.command("init")
@click.argument("backup", type=BACKUP)
@click.option("-o", "--output", type=click.Path(path_type=Path), help="File to write.")
def gaps_init(backup: Path, output: Path | None) -> int:
    """Seed known-gaps/<course>.toml from the Moodle features with no OpenLMS equivalent."""

    course = _read(read_backup, backup)
    path = output or Path("known-gaps") / f"{course.slug}.toml"
    if path.exists():
        raise Failed(f"{path} exists: edit it, or delete it to seed it again.")
    path.parent.mkdir(parents=True, exist_ok=True)
    findings = predict_gaps(course)
    path.write_text(known_gaps.render(course, findings), encoding="utf-8")
    click.echo(f"Wrote {path} with {len(findings)} entr(y/ies): review each one.")
    return 0


@cli.group()
def e2e() -> None:
    """End-to-end test of a migration on a TEST course in a running Studio."""


@e2e.command("local-setup")
@click.argument("course_keys", nargs=-1, required=True)
@click.option("--no-create", is_flag=True, help="Don't create missing courses.")
@click.option("--lms-container", default="tutor_dev-lms-1", show_default=True)
@click.option("--cms-container", default="tutor_dev-cms-1", show_default=True)
def e2e_local_setup(course_keys, no_create, lms_container, cms_container) -> int:
    """Local tutor dev only: create the test courses and the checker's OAuth client.

    Prints the client id and a new secret as export lines. Use:
    eval "$(mbz2openlms e2e local-setup course-v1:OpsWerks+E2E+2026)"
    """
    import subprocess

    try:
        client_id, secret = e2e_local.setup(
            list(course_keys),
            lms_container,
            cms_container,
            not no_create,
            log=lambda m: click.echo(m, err=True),
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise Failed(f"local setup failed (is the tutor dev running?): {exc}") from exc
    click.echo(f"export M2O_CLIENT_ID={client_id} M2O_CLIENT_SECRET={secret}")
    return 0


@e2e.command("run")
@click.argument("backup", type=BACKUP)
@click.option("--course", "course_key", required=True, help="The TEST course (overwritten).")
@click.option("--studio", envvar="M2O_STUDIO_URL", help="Studio URL [M2O_STUDIO_URL].")
@click.option("--lms", envvar="M2O_LMS_URL", help="LMS URL [M2O_LMS_URL].")
@click.option("--ca-bundle", envvar="M2O_CA_BUNDLE", type=click.Path(exists=True, path_type=Path))
@click.option("--known-gaps", "gaps_path", type=click.Path(exists=True, path_type=Path))
@click.option("--rules", type=click.Path(exists=True, path_type=Path))
@click.option("--manual", is_flag=True, help="Pause for a person to do the follow-ups.")
@click.option("--no-break", is_flag=True, help="Skip breaking the course on purpose.")
@click.option("--allow-fail", multiple=True, help="Finding id that may fail (repeatable).")
@click.option("--cms-container", help="Local tutor only: also export and check the export.")
@click.option("--yes", is_flag=True, help="Don't ask before replacing the course content.")
@click.option("-o", "--output", type=click.Path(path_type=Path))
def e2e_run(
    backup, course_key, studio, lms, ca_bundle, gaps_path, rules, manual, no_break, allow_fail,
    cms_container, yes, output,
) -> int:  # fmt: skip
    """Convert BACKUP, import it into the TEST course, and test the runbook and the checker.

    Never point it at a real course: the import replaces its content.
    """
    if not yes:
        click.confirm(f"This replaces all content of {course_key}. Continue?", abort=True)
    archive, folder, _result = build_archive(backup, Options(), output)
    course = _read(read_backup, backup)
    gaps_file = gaps_path or known_gaps.default_path(course)
    run = E2E(
        client=client(studio, lms, ca_bundle),
        course_key=course_key,
        moodle=course,
        known_gaps=known_gaps.load(gaps_file) if gaps_file.is_file() else [],
        rules=Rules.load(rules),
        out=folder / "e2e",
        due=default_due(),
        allow_fail=set(allow_fail),
        log=click.echo,
        pause=(lambda msg: click.prompt(msg, default="", show_default=False)) if manual else None,
    )
    export = None
    if cms_container:
        export = lambda dest: e2e_local.export(cms_container, course_key, dest)  # noqa: E731
    try:
        ok = run.run(archive, breaks=not no_break, export=export)
    except MigratedError as exc:
        raise Failed(str(exc)) from exc
    click.echo(f"{'PASS' if ok else 'FAIL'}: {sum(s.ok for s in run.steps)}/{len(run.steps)} steps")
    return 0 if ok else 1


def client(studio: str | None, lms: str | None, ca_bundle: Path | None):

    client_id = os.environ.get("M2O_CLIENT_ID")
    secret = os.environ.get("M2O_CLIENT_SECRET")
    if not (studio and lms and client_id and secret):
        raise Failed(
            "Studio API mode needs --studio/M2O_STUDIO_URL, --lms/M2O_LMS_URL, and "
            "M2O_CLIENT_ID and M2O_CLIENT_SECRET in the environment."
        )
    try:
        return StudioClient(studio, lms, client_id, secret, ca_bundle)
    except MigratedError as exc:
        raise Failed(str(exc)) from exc


def _read(reader, backup: Path):
    try:
        return reader(backup)
    except ArchiveError as exc:
        raise Failed(str(exc)) from exc


if __name__ == "__main__":
    sys.exit(main())
