# mbz2openlms

Moodle → OpenLMS course migration and checker.

Migrates Moodle courses to OpenLMS (our Open edX, Ulmo), and checks the result.

- `mbz2openlms convert` turns a Moodle course backup (`.mbz`) into a course archive to import in
  Studio, plus a report of the manual follow-ups.
- `mbz2openlms check` compares the migrated course with the Moodle backup (structure, content,
  quizzes, assignments, grading, files, prerequisites, dates, the OpenLMS review rules) and
  reports every difference. Accepted differences are reported as known gaps.

**Instructors:** follow [docs/runbook.md](docs/runbook.md). Nothing else is needed.

| Document | For |
|---|---|
| [docs/runbook.md](docs/runbook.md) | Migrating a course, step by step, with troubleshooting |
| [docs/checker.md](docs/checker.md) | What the checker compares, known gaps, review rules, API mode, end-to-end test |
| [docs/route-decision.md](docs/route-decision.md) | Why this route, compared with the alternatives |
| [docs/inventory-and-mapping.md](docs/inventory-and-mapping.md) | The pilot course (Linux Fundamentals): inventory, mapping, gaps |
| [docs/handover.md](docs/handover.md) | Handover walkthrough, acceptance checklist, sign-off |

## Quick start

Install the command once, from the clone (details and updating: runbook step 0):

```bash
uv export --frozen --no-dev --no-hashes --no-emit-project -o /tmp/mbz2openlms-pins.txt
uv tool install --editable . -c /tmp/mbz2openlms-pins.txt
```

Then, from any folder (output always goes to the repository's `out/<course>/`):

```bash
mbz2openlms convert ~/Downloads/backup-moodle2-course-131-....mbz
# Studio: create the course, Tools › Import the .tar.gz, do the follow-ups, Tools › Export
mbz2openlms check ~/Downloads/backup-...mbz --export ~/Downloads/course.xxxx.tar.gz
```

| Command | Does |
|---|---|
| `inventory <backup>` | `inventory.md` (shareable) and `inventory.json` (internal) |
| `convert <backup>` | The archive, `conversion-report.md`, and the inventory |
| `check <backup> --export <tar.gz>` / `--course <key>` | `check-report.md` and `check.json`; exit 0 PASS, 1 FAIL, 2 error |
| `gaps init <backup>` | Seeds `known-gaps/<course>.toml` for review |
| `e2e run` / `e2e local-setup` | End-to-end test on a test course in a running Studio (developers) |

`out/`, `*.mbz`, `*.imscc` and `*.tar.gz` are gitignored: they hold course content and answer
keys.

## Development

Developers work in the clone with `uv sync` and `uv run …`. The installed command runs the same
code, since the install is editable.

```bash
uv sync
uv run pytest                                          # synthetic backup, fake Studio
M2O_SAMPLE_MBZ=~/Downloads/<course 131>.mbz uv run pytest   # also the real pilot course
uv run ruff check . && uv run ruff format --check .
```

See [CLAUDE.md](CLAUDE.md) for the code layout and the invariants.
