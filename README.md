# Course Study Skills

Four coordinated [Codex](https://developers.openai.com/codex/skills) skills for course self-study and exam preparation.

The bundle is designed for learning from lecture notes, slides, handwritten notes, prescribed texts, teacher exercises, past papers, marking schemes, and revision materials. It keeps one course plan and separates teaching, evidence-based exam analysis, and question design so that these responsibilities do not conflict.

## Included skills

| Skill | Use it for |
| --- | --- |
| `study-planner` | Main entry point: continue a course, select the next lesson or practice, and maintain a flexible, exam-aware plan with saved evidence. |
| `course-study` | Coherent university-style lessons, local prerequisite repair, and temporary concept or question help. |
| `exam-analysis` | Traceable analysis of course requirements, past papers, marking schemes, question types, and topic statistics. |
| `practice-builder` | Teacher- and past-paper-grounded exercises, variants, complete solutions, and checking notes. |

`study-planner` is the normal entry point. The other three skills can also be invoked directly for a focused task.

## Install

Use Codex on macOS or Linux with Python 3.11 or newer. The helpers use Python's standard library and POSIX file locking; no Obsidian plugin, API key, or local project-specific files are required. Codex still needs permission to read your materials and write your chosen course-record directory.

Install all four folders together: their documentation and helpers use relative paths to the shared planning skill. For a fresh installation:

```bash
git clone https://github.com/tony-creat06/course-study-skills.git
cd course-study-skills
git checkout v0.2.8
mkdir -p ~/.codex/skills
cp -R skills/study-planner skills/course-study skills/exam-analysis skills/practice-builder ~/.codex/skills/
```

Alternatively, download `course-study-skills-v0.2.8.zip` from the [v0.2.8 release](https://github.com/tony-creat06/course-study-skills/releases/tag/v0.2.8), extract it, and copy all four folders inside `skills/` to `~/.codex/skills/`. GitHub's automatic source-code archives add a repository root folder; the uploaded bundle starts directly with `skills/`, `tests/`, `README.md` and `LICENSE`.

Codex's built-in Skill Installer can also install all four paths from this repository at ref `v0.2.8`: `skills/study-planner`, `skills/course-study`, `skills/exam-analysis`, and `skills/practice-builder`. The new skills are available on the next turn; restart Codex if they do not appear.

If a destination skill already exists, back up all four folders and preserve any personal edits before replacing them together. Finish or abort any pending course-record bundle using the current writer first. Keep personal course records in their own directory; upgrading the skills does not require changing them. An already downloaded older ZIP stays at its old version; download this release again to upgrade.

## Start studying

For an existing course with saved records:

```text
$study-planner 继续学习课程 X，读取已有课程记录并安排下一段。
```

For a new course, state the course identity, where its materials are, and where you want the separate learning records saved:

```text
$study-planner 我想从零学习课程 X。资料在 <path>；请把学习记录保存到 <path>。
```

The skills treat learner-provided materials as the primary source. Recent two to three years of past papers are the highest-priority evidence for exam style; teacher exercises establish course emphasis; older papers are secondary. AI-authored variants and new questions supplement the limited supply of original questions, and are explicitly labelled as such.

## What is included and excluded

This repository contains only the reusable skill instructions and their small standard-library Python helpers. It does not contain lecture notes, past papers, answers, personal progress, student work, or other course materials.

This is version 0.2.8. Related exam records, profiles and statistics are now saved as a recoverable `analyst` bundle. The planner reads them with `read-set`, which holds the writer's lock across all requested files, then passes the same evidence snapshot to teaching and question design. Interrupted publication blocks shared reads until recovery. Analysts may recover their own exam bundle; only the planner's `main` role can change the shared plan or checkpoint. The current writer also recovers older v1 main journals.

The planner compares source-backed question styles, ability chains and observed mark allocations with existing teaching and practice, then records specific supplements and their actual coverage. History, partial-paper marks and personal priorities remain distinct. Summary fields preserve joint allocations and source parts; missing style labels stay unclassified. When the exam is near and time is insufficient, the planner changes the same plan, prioritizes the necessary teaching and practice, and records deferred depth for later completion. Analysis supplies evidence rather than maintaining a competing schedule.

Numeric unclosed-formula and common raw-LaTeX checks, author solutions versus student delivery, and recoverable learning-record saves remain included. Writing and `read-set` support POSIX locking on macOS/Linux; Windows coordination has not been implemented or tested. A bundle updates files in sequence with explicit finish/abort recovery. The lock coordinates helper users; separate single-file writes and external editors do not automatically become a consistent exam publication. Content and source checks remain necessary. Complete any pending bundle before rolling back to an older writer, which cannot recover v2 journals. Existing course formats remain readable without migration.

The personal teaching-experience loop remains lightweight: reuse relevant strategies, record concrete feedback and problems, apply a small adjustment, and retain, revise or retire it from later observations. Each learner's strategies stay in their own records. Without new evidence, strategies can remain unchanged; each run is not guaranteed to improve learning.

Personalization uses local course records, not automatic rewriting of the shared skill source. Preferences can change or be withdrawn. Cross-course reuse requires the same learner and explicitly general preferences from designated records; personal records are not published with this bundle.

Helper regressions and bounded simulated use check software and workflow behavior. They do not establish superior learning, long-term retention, or exam results compared with direct-file tutoring. Important course-specific content still needs checking against the teaching materials.

## Development checks

Run `python3 -B -m unittest discover -s tests -v` for helper regressions. Mathematical note checks are read-only:

```bash
python3 skills/course-study/scripts/check_math.py <saved-lesson.md>
```

The text checker flags common delimiter, brace, and command-escaping mistakes. It does not render formulas or verify their meaning; inspect warnings in context. HTML checks catch common raw mathematical commands, not every possible TeX expression. Test data in this repository is synthetic and contains no learner records or course PDFs. Record tests include real subprocess interruptions of main and analyst bundles, recovery, stale writes, manual edits, role boundaries and a reader waiting for a complete exam batch. Release checks run on macOS; Linux uses the same POSIX interfaces but has not received a separate native Linux run. Simulated platform fallback tests do not establish Windows support.

## Design references

The workflow adapts specific ideas from [Revision Tutor](https://github.com/yangcodingmaster/Revision-Tutor/blob/main/SKILL.en.md) (local reasoning gaps), [OpenTutor](https://github.com/LEARNableLabs/opentutor/blob/main/docs/methodology.md) (concrete revisit and variation tasks), and [DeepTutor](https://arxiv.org/html/2604.26962v3) (source grounding and separate tutoring/practice evaluation). These inform the design; their reported evaluations do not validate this bundle. Coherent lectures, optional in-class checks, and most practice after class remain the defaults.

The [IES study guide](https://ies.ed.gov/ncee/wwc/practiceguide/1) informs the combination of worked examples and problem solving. [Carnegie Mellon's learning principles](https://www.cmu.edu/teaching/principles/learning.html) inform targeted feedback and practice that integrates skills and requires choosing when to apply them. These are design grounds, not evidence that this bundle improves an individual student's outcomes.

The [learning-styles evidence review](https://journals.sagepub.com/doi/10.1111/j.1539-6053.2009.01038.x) informs the distinction between expressed presentation preferences and evidence that a matching teaching method improves learning. Preference updates do not assign fixed learner types or establish effectiveness by themselves.

[ACE](https://github.com/ace-agent/ace) informs incremental experience accumulation, [Reflexion](https://github.com/noahshinn/reflexion) informs concrete failure feedback for a later attempt, and [GEPA](https://github.com/gepa-ai/gepa) informs checking proposed changes and retaining earlier strengths. These ideas are adapted into local learner records; their frameworks are not dependencies and their evaluations do not establish teaching gains here.

## License

MIT. See [LICENSE](LICENSE).
