# The checker: what `mbz2openlms check` compares

`check` compares a migrated course in OpenLMS with its Moodle backup and reports every
difference, so a migration doesn't need a manual review.

The expectations come from the Moodle backup and the mapping rules in `src/mbz2openlms/check/`.
**Nothing comes from the converter**, so a converter bug can't hide itself.
`tests/test_invariants.py` enforces that the checker never imports `convert/` or `olx/`.

## What it compares

| Check | Compares | Fails when |
|---|---|---|
| structure | Every section and learner-facing activity is in OpenLMS, by title; no extra sections or units; in API mode, everything is published | A section or activity is missing, or a unit was added; a unit was never published |
| content | Text of pages, labels, book chapters, intros and summaries (95% of the Moodle words, in order); URLs; agreement statements; survey questions | Text, a link, a statement or a rating question is missing |
| quizzes | Each question: text, answers and which are correct, weight (marks), attempts. Random questions: a Problem Bank showing the same number from a pool of the same size, and every pool question. Essays: an ORA with the prompt and the marks | Any answer key, mark or pool differs |
| assignments | An ORA with the instructions, the same submission types (file, text, number of files), and the points | Submission types differ (points: warning) |
| grading | Each graded activity's share of the course grade; the pass cutoff | A share or the cutoff differs |
| prerequisites | Each "complete X first" restriction is a prerequisite at 100% | Missing, wrong, or below 100% (export mode: not checked) |
| dates | Graded and dated subsections and assignments have a future due date | A due date is in the past (missing: warning) |
| files | Every file Moodle content embeds is uploaded; every `/static/` link resolves | A file is missing |
| review rules | `review-rules.toml`: external hosts, `<iframe>`/`<embed>`, scripts, `javascript:` links, links back to Moodle, leftover Moodle file links, blocked component types, credentials (passwords, keys, tokens), plain `http://`, broken relative links | Credentials, scripts, embeds from unlisted hosts, Moodle leftovers, blocked components (unlisted hosts, `http://` and relative links are warnings) |
| gaps | Moodle features with no OpenLMS equivalent: unsupported activity types and question types, time limits, quiz security, free-text survey questions, date and other restrictions | Always, unless listed as a known gap |

Reports never contain answer keys: answers are compared and only counted. Credentials are shown
truncated. Text that holds a credential is left out of the content comparison, because the
runbook has it rewritten.

## Statuses

`fail` (exit status 1), `warn`, `known gap` (a listed, accepted difference), `not checked`
(can't be read from this source), `pass`. Every finding has a stable id such as
`time-limit|quiz 'Quiz'` or `prereq|quiz 'Quiz'`; `check.json` has them all, passes included.

## Known gaps

`known-gaps/<course slug>.toml` lists accepted differences:

```toml
[[gap]]
id = "time-limit|quiz 'Quiz'"
reason = "Timed exams are off on OpenLMS (platform decision, 2026-10)"
```

A failing or warning finding with a listed id becomes a known gap. The report lists entries that
match nothing, or whose check now passes, as stale. `mbz2openlms gaps init <backup>` seeds the
file from what the Moodle backup alone predicts. It never overwrites an existing file. Each
course's file is reviewed by Bay and Geo ("Reviewed by:" at the top).

## Review rules

`review-rules.toml` (or `--rules <file>`):

```toml
[links]
allowed_hosts = ["learn.kodekloud.com"]  # exact host names, reviewed

[blocks]
blocked = ["lti_consumer", "jsinput", ...]  # always fail
allowed = ["html", "problem", ...]          # others: warning
```

**Provisional:** the OpenLMS course review-rules document has not been delivered. Until it is,
no host is allowed, so every external link is a warning for reviewers. Credentials, scripts,
embeds and Moodle leftovers fail regardless.

## Where it reads the migrated course from

### Studio export (instructor default)

`--export <course.tar.gz>` from Studio's **Tools › Export**. It needs no credentials. It can't
show subsection prerequisites: Open edX keeps them in the milestones tables, not in the OLX. They
are reported as "not checked", and the runbook has a checklist step for them. An export also
can't tell draft from published content.

### Studio API mode

`--course <course key>`, with an OAuth client (client-credentials grant) whose service user has
the **Staff** role on the course:

```bash
export M2O_CLIENT_ID=... M2O_CLIENT_SECRET=...
export M2O_STUDIO_URL=https://openlms-studio.werkslearning-preprod.opswerks.com
export M2O_LMS_URL=https://openlms.werkslearning-preprod.opswerks.com
uv run mbz2openlms check <backup.mbz> --course course-v1:OpsWerks+A11-FND-LNX01+2026
```

It reads:

| API | Gives |
|---|---|
| `GET /api/contentstore/v1/course_index/<course>` | Outline; per subsection `prereq`, `prereq_min_score`, `due`, `graded`, `format`; per unit `published`, `has_changes` |
| `GET /api/contentstore/v1/course_grading/<course>` | Grading policy and cutoffs |
| `GET /api/olx-export/v1/xblock/<unit>/` | Each unit's OLX with its components inline, including Problem Banks and answer keys |

On Ulmo, `olx-export` serves file links as `/assets/courseware/v1/<hash>/asset-v1:…+type@asset+block/<name>`.
The reader turns them back into `/static/<name>` and confirms each one with a `HEAD` request, so
both sources give the same model. The API returns Studio's draft, so units with unpublished
changes are flagged.

API mode suits CI and the platform team. Issuing an OAuth client for it is a credentials
review item.

## End-to-end test (developers)

`mbz2openlms e2e run <backup> --course <TEST course key>` tests the converter, the runbook and
the checker against a running Studio. It is not a migration path: it **replaces the test course's
content**. The steps:

1. import the archive;
2. check that the follow-ups are reported missing;
3. apply them through the API (prerequisites at 100%, due dates in 30 days, credential lines
   rewritten), or `--manual` pauses for a person;
4. check that it passes;
5. break the course on purpose (a changed answer, as a draft and then published; a
   prerequisite below 100%; a past due date), check each break is caught, and restore it;
6. with `--cms-container`, export and check the export (local tutor only).

On the local tutor dev:

```bash
eval "$(uv run mbz2openlms e2e local-setup course-v1:OpsWerks+MBZ_E2E+2026)"
export M2O_STUDIO_URL=https://studio.local.openedx.io M2O_LMS_URL=https://local.openedx.io
export M2O_CA_BUNDLE=<OpenLMS repo>/.tutor/data/caddy_dev/data/caddy/pki/authorities/local/root.crt
uv run mbz2openlms e2e run <backup.mbz> --course course-v1:OpsWerks+MBZ_E2E+2026 \
  --cms-container tutor_dev-cms-1
```

Last result on the local tutor (Tutor 21.0.4, Ulmo), course 131: **PASS, 10 of 10 steps**
(2026-10-28).
