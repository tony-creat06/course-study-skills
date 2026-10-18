# Course Study Skills

Five coordinated [Codex](https://developers.openai.com/codex/skills) skills for course self-study and exam preparation.

The bundle is for sustained, systematic course teaching from a usable set of lecture notes, slides, classroom transcripts, handwritten notes, prescribed texts, teacher exercises, past papers, marking schemes, and revision materials. Uploading a complete term in advance is not required. Lab procedures, apparatus operation, risk assessments, experimental data, lab reports and isolated questions do not implicitly start the suite. Explicit component invocation remains available. It keeps one course plan and separates teaching, evidence-based exam analysis, and question design so that these responsibilities do not conflict.

## Included skills

| Skill | Use it for |
| --- | --- |
| `study-planner` | Main entry point: continue a course, select the next lesson or practice, and maintain a flexible, exam-aware plan with saved evidence. |
| `course-study` | Coherent university-style lessons, local prerequisite repair, and temporary concept or question help. |
| `exam-analysis` | Traceable analysis of course requirements, past papers, marking schemes, question types, and topic statistics. |
| `practice-builder` | Teacher- and past-paper-grounded exercises, variants, complete solutions, and checking notes. |
| `study-notes` | Bilingual concepts, terms, exam expressions and derivations from the other modules' saved feedback; complete offline chapter notes, course-end synthesis and optional PDF export. |

`study-planner` is the normal entry point. The other four skills can also be invoked directly for a focused task.

## Install

Version **v0.3.1** contains all five skills. Use Codex on macOS or Linux with Python 3.11 or newer. The helpers use Python's standard library and POSIX file locking; no Obsidian plugin, API key, or project-specific development files are required. Codex needs permission to read your materials and write the course-record directory you choose. Check `python3 --version` first; if it is older than 3.11, use a supported Python interpreter for the commands below.

Install all five folders together in the same skills directory: they use relative paths to shared helpers. For a fresh user-wide installation, use Codex's documented `~/.agents/skills/` directory:

```bash
git clone https://github.com/tony-creat06/course-study-skills.git
cd course-study-skills
git checkout v0.3.1
mkdir -p ~/.agents/skills
cp -R skills/study-planner skills/course-study skills/exam-analysis skills/practice-builder skills/study-notes ~/.agents/skills/
```

Alternatively, download `course-study-skills-v0.3.1.zip` from the [v0.3.1 release](https://github.com/tony-creat06/course-study-skills/releases/tag/v0.3.1), verify it against the accompanying SHA256 file, extract it, and copy all five folders inside `skills/` to the same destination. The uploaded bundle starts directly with `skills/`, `tests/`, `README.md` and `LICENSE`; GitHub's automatic source archives add a repository root folder.

Codex's built-in Skill Installer can also install all five repository paths at ref `v0.3.1`: `skills/study-planner`, `skills/course-study`, `skills/exam-analysis`, `skills/practice-builder`, and `skills/study-notes`. Select one common destination for the five folders.

For an upgrade, use the directory from which your existing skills are loaded, including `~/.codex/skills/` on installations already using that location. Do not create a second copy with the same names in another searched directory. Back up all five folders, preserve personal edits, and replace the bundle together. Finish or abort pending course-record bundles using the current writer before replacement. Keep course materials and personal learning records outside the installed skills; upgrading does not require migrating those records. Older downloaded ZIPs retain their original version.

Codex detects skill updates automatically; if the changes do not appear, restart it. See the [official skills and loading instructions](https://learn.chatgpt.com/docs/build-skills). The historical [v0.2.8 release](https://github.com/tony-creat06/course-study-skills/releases/tag/v0.2.8) remains available as the four-skill version.

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

Version 0.3 adds complete chapter/course notes and the material-intake workflow to the v0.2.8 evidence baseline. Patch 0.3.1 fixes currency-text rejection, protects scratch outputs from overwrites, and verifies the rendered note input under the publication lock. Scratch outputs require a new `.html` filename for notes/reviews or `.json` for statistics; shared updates keep the existing version-checked mode. Related exam records, profiles and statistics are saved as a recoverable `analyst` bundle. The planner reads them with `read-set`, which holds the writer's lock across all requested files, then passes the same evidence snapshot to teaching and question design. Interrupted publication blocks shared reads until recovery. Analysts may recover their own exam bundle; only the planner's `main` role can change the shared plan or checkpoint. The current writer also recovers older v1 main journals.

The planner compares source-backed question styles, ability chains and observed mark allocations with existing teaching and practice, then records specific supplements and their actual coverage. History, partial-paper marks and personal priorities remain distinct. Summary fields preserve joint allocations and source parts; missing style labels stay unclassified. When the exam is near and time is insufficient, the planner changes the same plan, prioritizes the necessary teaching and practice, and records deferred depth for later completion. Analysis supplies evidence rather than maintaining a competing schedule.

Numeric unclosed-formula and common raw-LaTeX checks, author solutions versus student delivery, and recoverable learning-record saves remain included. Writing and `read-set` support POSIX locking on macOS/Linux; Windows coordination has not been implemented or tested. A bundle updates files in sequence with explicit finish/abort recovery. The lock coordinates helper users; separate single-file writes and external editors do not automatically become a consistent exam publication. Content and source checks remain necessary. Complete any pending bundle before rolling back to an older writer, which cannot recover v2 journals. Existing course formats remain readable without migration.

The personal teaching-experience loop remains lightweight: reuse relevant strategies, record concrete feedback and problems, apply a small adjustment, and retain, revise or retire it from later observations. Each learner's strategies stay in their own records. Without new evidence, strategies can remain unchanged; each run is not guaranteed to improve learning.

Personalization uses local course records, not automatic rewriting of the shared skill source. Preferences can change or be withdrawn. Cross-course reuse requires the same learner and explicitly general preferences from designated records; personal records are not published with this bundle.

Helper regressions and bounded simulated use check software and workflow behavior. They do not establish superior learning, long-term retention, or exam results compared with direct-file tutoring. Important course-specific content still needs checking against the teaching materials.

## Materials and course files

Each course has a declared material archive and a separate record/output root. Recommended intake is `<project>/inputs/course-materials/<course>/inbox/`: drop new files there, or provide them in chat. The next course resumption scans the intake, classified folders and declared original source roots for added, modified, missing, moved and duplicate content. There is no background watcher. Physical folders separate syllabus, lectures, transcripts, exercises, solutions, exams, revision, textbooks and supplements; a source/chapter index relates pages and timestamps without duplicating files per chapter. Classification follows inspected content, not filenames alone.

`study-planner/scripts/course_files.py` provides version-checked `init`, `scan`, `import` and `index` commands; see `skills/study-planner/references/course-files.md` for the exact internal inputs and outputs. External original files remain unchanged. Managed intake files leave the inbox only after archive and registry verification; same-name new versions retain separate bytes. Source changes trigger review of related evidence, not erasure of prior learner records or automatic rewriting of every analysis.

Raw ASR transcripts retain their words and timestamps. Teaching may interpret likely recognition errors using context and corresponding notes; ambiguous terminology, numbers, negations or equations retain the original wording and location in a separate interpretation record.

`index.html` and `index.md` are the visible course entry points. Notes stay in `notes/`, new question prompts in `questions/prompts/`, author solutions in `questions/solutions/`, actual attempts in `practice/`, and completed/shown-solution reviews in `reviews/`. Exam/question analysis also publishes a concise learner report at `exam/brief.md`, covering actual source scope, topics, styles, abilities and gaps. Detailed annotations, profiles and statistics stay in the course workspace; the navigation links only the brief. The analyst publishes it with the associated evidence as one recoverable batch. Uncreated outputs are labelled as such. The default index excludes unreleased author solutions and old combined records with unknown answer exposure. Existing course paths and historical work remain intact; the first eligible resumption adopts the file workflow without replaying lessons or inventing learner answers.

## Chapter and course notes

After each saved lesson, the planner hands existing feedback to `study-notes` to accumulate the corresponding chapter. A standalone lesson note is optional. The planner confirms when a chapter's taught scope is complete; partial chapters state their actual scope. After the course is completed, a course note reorganizes the chapters using the learning process and their connections. Students do not fill in another input form, and all four providers need not run again.

The note module writes only `notes/`, with its own `notes` role; the original roles retain ownership of plans, checkpoints, teaching, exams, questions and learner evidence. The renderer checks feedback and destination versions under the shared lock, preserves backups and refuses stale feedback/manual-edit overwrites. It does not publish hidden future solutions or infer mastery from reading.

New internal drafts use schema version 3: connected lecture sections with the complete core body visible by default, plus separate concise and optional recall views. Concepts, bilingual terminology, examples, English reference expressions and derivation steps belong in the narrative where they explain the subject. Only supplementary material is folded. Source-topic coverage maps locate input topics in the output; a valid map alone does not prove completeness or mathematical correctness. Versions 1 and 2 remain readable without migrating old records.

Each HTML file is self-contained: native MathML, embedded images, inline styles and local search. Desktop reading is primary, with a readable text measure, a persistent chapter index and local scrolling for wide equations. Optional bilingual term/symbol indexes and numbered key equations link back to the full explanations. Concise views retain the starting relationships, method choices, conditions and uses rather than extracting only final results. Basic narrow-screen support is auxiliary. Print/Save PDF includes the full body and supplements, then restores the reading state; annotated PDF snapshots are not overwritten. File/version tests do not establish content accuracy or learning gains.

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
