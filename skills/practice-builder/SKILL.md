---
name: practice-builder
description: Select or create course-grounded practice questions, variants, worked solutions and reference marking points. Use within an established systematic course or when explicitly invoked; isolated questions and lab/report tasks do not implicitly activate this suite. study-planner handles delivery, feedback and scheduling.
---

# 题目与解析

根据课程资料与考试依据设计可用练习，每题明确知识点与所测能力，先解后核再交付；**不自行制定学习路线、不预填学生作答或宣称学生掌握。**

## 边界与接收

1. **启用与路径**：遵循[共同记录约定](../study-planner/references/coordination.md)的系统课程范围；明确点名本 Skill 时可单独设计或核对题目。新课须先由主流程完成资料移动归档与索引，普通续学只取当前必要来源。严禁写入 `.codex/` 等隐藏目录。
2. **目标与支持阶梯**：沿用规划或用户指定的用途（课堂示范 / 课后小练 / 单元综合 / 模拟）、所测能力、已讲范围、薄弱点与时间限制；需要从示范过渡到独立解题或设计方法选择时读[练习支持与方法选择](references/practice-progression.md)。
3. **文件分离**：新题干保存于 `questions/prompts/<ID>.md`，对应完整作者解析保存于 `questions/solutions/<ID>.md`（沿用同一稳定 ID；既有旧路径保留）；临时答疑优先直接讲解并记 `side-notes/`。

## 选题来源与设计准则

1. **优先级与锚点**：最近两三年真题作考试风格最高参考，老师习题定重点与要求，更早真题次要；AI 变式与新题补足题量，**必须明示来源类型**（原题 / 有锚点变式 / 自拟题），自拟不冒充真题。
2. **有效变式与迁移检验**：变式写清保留与改变之处，避免仅换数字套路；迁移检验须真正改变依赖关系、适用条件或表示，让学生作新判断。可保留少量未曝光原题供后续观察，但用户要求讲解时照常讲，由规划另选观察题。
3. **题干自足与考试对齐**：按原卷和目标选用题型（选择干扰项须对应真实误解，不强求全学科四选一），确保条件、图表、符号与允许结果自足；综合练习按[考试依据交接](../study-planner/references/exam-handoff.md)返回能力链、题型与分值对应及未覆盖项。

## 解析核对与交付边界

1. **先解题再定稿**：保存关键思路、必要中间步骤、结论/单位、适用条件与参考评分点（区分官方评分标准与推定评分点；合理替代论证均认可）。原题或答案存疑时按[共同核对规则](../course-study/references/source-checks.md)处理，不输出存疑题冒充可靠练习。
2. **多维交叉核对**：按题型核对条件充分性、多解边界、符号维度、数值极限与来源一致性，必要时用另一解法或计算工具交叉验算；复杂自拟题做“仅看题干”的独立可解性复核，记录实际核对范围与未知项。
3. **不剧透交付**：沿用主流程 `run ID`（独立出题先跑 `course_delivery.py begin`）。向规划交付题干/解析路径、能力映射与核对说明；**独立尝试时只向学生展示题干**，提示与作者解析按作答反馈或明确请求开放；提供给 `study-notes` 时严禁泄露未展示解析。
