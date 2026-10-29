# Conversion: Synthetic Linux (SYN-LNX 01)

From `backup-moodle2-course-syn-lnx-01` to `syn-lnx_01-2026.tar.gz` (course key as built: `course-v1:OpsWerks+SYN-LNX_01+2026`; Studio import keeps the key of the course you import into).

## Created

|  | Count |
|---|---|
| sections | 3 |
| subsections | 8 |
| units | 10 |
| static files | 1 |
| html | 6 |
| openassessment | 2 |
| problem | 10 |
| itembank | 1 |
| survey | 1 |

## Where each activity went

| Moodle | OpenLMS |
|---|---|
| page 'Welcome' | Intro › Welcome |
| url 'Docs' | Intro › Welcome |
| book 'Materials' | Intro › Materials |
| assign 'Upload' | Intro › Upload |
| forum 'Chat' | Intro › Chat |
| feedback 'Agreement' | Assessment › Agreement |
| quiz 'Exam' | Assessment › Final |
| quiz 'Practice quiz' | Assessment › Practice |
| feedback 'Survey' | Survey › Survey |

## Grading

| Assignment type | Weight |
|---|---|
| Assignment | 33% |
| Exam | 67% |
| Integrity Agreement | 0% |

Pass cutoff: 50%.

## Manual follow-up in Studio

Do these in Studio after the import, then run `mbz2openlms check`.

1. **page 'Welcome'**: Embedded file 'gone.png' is not in the backup: upload it in Files & Uploads and fix the link.
2. **page 'Welcome'**: Link to another Moodle item ($@QUIZVIEWBYID*20@$) removed: re-link it.
3. **page 'Welcome'**: Possible password or key assignment ('password: Hun…'): remove it or replace it with a placeholder in Studio. The checker fails until it is gone.
4. **forum 'Chat'**: 'forum' activities are not converted: rebuild it by hand.
5. **quiz 'Exam' question 'Match'**: Question type 'match' is not converted: rebuild it in Studio.
6. **subsection 'Final'**: Set prerequisite 'Agreement' with minimum score 100% (Studio › subsection › Configure › Access). Moodle required it to be completed first.
7. **feedback 'Survey'**: Free-text question not converted: 'What would you change?'.
8. **subsection 'Survey'**: Moodle required completing 'Final', 'Upload'. OpenLMS allows one prerequisite per subsection: choose one or leave it open.

## Not carried over

| Where | Detail |
|---|---|
| book 'Materials' | Hidden chapter 'Draft' is not converted. |
| feedback 'Agreement' | The 'page after submit' message is not converted. |
| quiz 'Exam' | Time limit of 30 min not set (timed exams are off). Convert again with --timed-exams once they are enabled. |

## For information

| Where | Detail |
|---|---|
| feedback 'Agreement' | Optional statement is now required: 'I will not use AI tools.…'. |
| quiz 'Exam' | Random selection kept: 'Exam: Easy questions' shows 2 of 3 problems to each learner. |

## Dates from the Moodle run

Not carried over: they belong to the old run. Set the new run's dates in Studio (subsection › Configure › Due date). Until a due date is set, answers and correctness that Moodle showed "after the quiz closed" stay hidden.

| Where | What | Moodle |
|---|---|---|
| assign 'Upload' | due | 2026-07-17 08:00 UTC |
| quiz 'Exam' | opens | 2026-07-17 08:00 UTC |
