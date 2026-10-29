# Check: Synthetic Linux (SYN-LNX 01)

**Result: ❌ FAIL**

Generated 2026-10-29T08:56:29+00:00. Moodle: `backup-moodle2-course-syn-lnx-01`. OpenLMS: Studio export `syn-lnx_01-2026.tar.gz`. Known gaps: `known-gaps/syn-lnx-01.toml`.

| Status | Count |
|---|---|
| ❌ Fail | 2 |
| ⚠️ Warning | 5 |
| 📝 Known gap | 7 |
| ⏸ Not checked | 1 |
| ✅ Pass | 41 |

## ❌ Fail

| Check | Where | Detail |
|---|---|---|
| review rules | Intro › Welcome › Welcome | Moodle link left over: @@PLUGINFILE@@/gone.png |
| review rules | Intro › Welcome › Welcome | possible password or key assignment: 'password: Hun…' |

## ⚠️ Warning

| Check | Where | Detail |
|---|---|---|
| dates | subsection 'Upload' | no due date set for the new run |
| dates | subsection 'Agreement' | no due date set for the new run |
| dates | subsection 'Final' | no due date set for the new run |
| dates | assign 'Upload' | no due date set for the new run |
| review rules | Intro › Welcome › Docs (+1 more) | external host not yet reviewed: docs.example.com |

## 📝 Known gap

| Check | Where | Detail |
|---|---|---|
| gaps | forum 'Chat' | Moodle 'forum' activities have no OpenLMS equivalent (accepted) |
| gaps | feedback 'Agreement' | optional statement is required in OpenLMS: 'I will not use AI tools.…' (accepted) |
| gaps | feedback 'Agreement' | 'page after submit' message has no OpenLMS equivalent (accepted) |
| gaps | quiz 'Exam' | time limit 30 min: not set (timed exams are off on OpenLMS) (accepted) |
| gaps | quiz 'Exam' | question type 'match' is not converted (accepted) |
| gaps | feedback 'Survey' | free-text question has no OpenLMS equivalent: 'What would you change?' (accepted) |
| prerequisites | feedback 'Survey' | Moodle needs 'Final', 'Upload' completed; OpenLMS allows one prerequisite per subsection — accepted: Moodle needs 'Exam', 'Upload' completed; OpenLMS allows one prerequisite per subsection |

## ⏸ Not checked

| Check | Where | Detail |
|---|---|---|
| prerequisites | quiz 'Exam' | subsection 'Final' should require 'Agreement' at 100%: not in a Studio export, check it in Studio (runbook checklist) |

## Passed

| Check | Passed |
|---|---|
| structure | 13 |
| content | 10 |
| quizzes | 11 |
| assignments | 2 |
| grading | 3 |
| files | 1 |
| review rules | 1 |

Every finding, passes included, is in `check.json`. To accept a difference, add its `id` from there to the known-gaps file with a reason, and have it reviewed.
