# Linux Fundamentals (course 131): inventory and Moodle → OpenLMS mapping

Source: Moodle course 131 "Linux Fundamentals" (`A11-FND-LNX01`), Moodle 5.1.1, backed up
2026-10-27 without user data. Built with `mbz2openlms inventory`; run it again for the full
report (`out/a11-fnd-lnx01/inventory.md`).

## What is in the course

| | Count |
|---|---|
| Sections / subsections | 3 / 3 |
| Activities | 14: 4 Feedback, 3 Quiz, 3 Subsection, 1 Book (2 chapters), 1 Assignment, 1 Page, 1 Question bank |
| Questions | 57 bank entries (157 saved versions): 54 multiple choice (one answer), 2 description, 1 essay |
| Files | 1 image (in the backup) |
| External links | 13, to `learn.kodekloud.com`, `engineer.kodekloud.com`, `github.com`, `www.linode.com` |

57 questions, not 157: since Moodle 4 every saved edit is a new version of the same question.

## Outline and where each item goes

| Moodle | OpenLMS | Status |
|---|---|---|
| **📚 Linux Fundamentals** (section) | Section | ✅ |
| Learning Materials (Book, 2 chapters) | Subsection, one unit per chapter | ✅ |
| KKE Completion (Assignment: image upload, up to 2 files of 2 MB, ungraded) | Subsection with an ungraded ORA (image upload, multiple files) | ⚠️ staff review instead of Moodle grading |
| Linux Fundamentals (Question bank) | Not learner-facing | — |
| **📝 Assessment** (section) | Section | ✅ |
| Mock Practical (subsection) → Integrity Agreement - Mock Practical (Feedback) | Subsection "Integrity Agreement - Mock Practical": checkbox problem, every box required, graded at 0% | ⚠️ |
| → Mock Practical (Quiz: instructions only, grade 0, 2 h) | Subsection "Mock Practical" with the instructions; prerequisite: the agreement at 100% | ⚠️ time limit dropped |
| Quiz (subsection) → Integrity Agreement - Quiz | Subsection with the agreement problem | ⚠️ one optional statement becomes required |
| → Quiz (22 random questions, 1 h, 1 attempt, graded) | Subsection "Quiz": Problem Bank 19 of 20 "Easy" (1 point each) + Problem Bank 3 of 7 "Medium" (2 points each); prerequisite: the agreement | ⚠️ time limit dropped |
| Practical (subsection) → Integrity Agreement - Practical | Subsection with the agreement problem | ⚠️ |
| → Before you begin (Page, gated on the agreement and a 3-hour window) | Unit in subsection "Practical" | ⚠️ time window → subsection dates |
| → Practical (Quiz: 1 essay, 80 marks, 2 h) | ORA in subsection "Practical", staff-graded, rubric out of 80 | ⚠️ time limit dropped |
| **💚 Thanks for the feedback!** (section) → Feedback (4 ratings, 2 free text) | Subsection with a Survey component (4 ratings) | ⚠️ free text dropped; four-way restriction can't be expressed |

## Grading

Natural aggregation: Quiz and Practical are 100 points each, so **50% / 50%**. KKE Completion
and Mock Practical aren't graded. Both graded items have a pass mark of 85, so the course pass
cutoff is **85%**. The three agreements are graded at 0% of the course grade: Open edX unlocks a
subsection on the *graded* score of its prerequisite.

## Manual follow-ups the conversion lists

1. Three prerequisites at 100%: Mock Practical, Quiz and Practical each need their agreement.
2. "Before you begin" contains the lab login line ("Enter your password: …"). It is flagged as a
   credential and must be rewritten in Studio. **Decision for Bay/Geo:** what the line should
   say instead (for example "Your instructor gives you the lab password").
3. "Before you begin" has a relative link (`/cdn/assets/sprites-core-…svg`) that is already
   broken in Moodle: remove it.
4. Two free-text survey questions and the four-way restriction on the final Feedback: known gaps.
5. Due dates for the new run on every graded or dated subsection and on the KKE Completion ORA.

## Known gaps

Accepted differences, listed in [`known-gaps/a11-fnd-lnx01.toml`](../known-gaps/a11-fnd-lnx01.toml)
(awaiting Bay/Geo review):

| Gap | Why |
|---|---|
| Quiz time limits (1 h, 2 h, 2 h) | Timed exams are off on OpenLMS. Platform decision; `--timed-exams` keeps them once enabled |
| "Page after submit" message of the three agreements | No Open edX equivalent |
| One optional agreement statement becomes required | A checkbox problem can't have an optional box and still require the rest |
| "Before you begin" time window (2026-07-20 01:00–04:00 UTC) | No per-unit dates; use the Practical subsection's release and due dates |
| Two free-text survey questions | The Survey component has rating questions only |
| Final Feedback needs four activities completed | Open edX allows one prerequisite per subsection |

Learner data (enrolments, attempts, grades, submissions) is out of scope and is not in the
backup.

## Moodle features in general

The full feature table (every Moodle activity and question type, its OpenLMS target and status)
is `ACTIVITIES` and `QTYPES` in [`src/mbz2openlms/mapping.py`](../src/mbz2openlms/mapping.py).
The runbook's "What carries over" table summarises it for instructors. Not converted, and
listed as manual follow-ups when a course has them: forum, choice, lesson, workshop, H5P,
SCORM, LTI, glossary, wiki, database, and the matching, cloze and drag-and-drop question types.
