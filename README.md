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

Install all four folders together: their documentation uses relative links to the shared planning skill.

```bash
git clone https://github.com/<your-account>/course-study-skills.git
cd course-study-skills
cp -R skills/study-planner skills/course-study skills/exam-analysis skills/practice-builder ~/.codex/skills/
```

Alternatively, Codex's built-in Skill Installer can install the folders individually from GitHub. Use the paths `skills/study-planner`, `skills/course-study`, `skills/exam-analysis`, and `skills/practice-builder` from this repository. Restart Codex if the new skills do not appear automatically.

If a destination skill already exists, back it up first instead of overwriting it blindly.

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

This is version 0.2.2. It was structurally checked and exercised in a bounded simulated workflow. It has not yet had broad human classroom validation, so use it as a study aid and verify important course-specific content against your teaching materials.

## License

MIT. See [LICENSE](LICENSE).
