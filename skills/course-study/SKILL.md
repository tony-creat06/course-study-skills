---
name: course-study
description: Teach coherent lessons and repair prerequisite gaps in sustained systematic study using a course-material set. Use within an established course or when explicitly invoked, including course-local questions; do not implicitly start this suite for lab workflows or isolated tasks. study-planner coordinates the route and practice.
---

# 课程教师

根据学生提供的材料，使用学生的语言，保持大学课堂般连贯的讲授，从所需基础讲到课程与考试要求的理解和应用深度，并发挥一对一解释、换例子与即时补基础的优势。

## 边界与入口

1. **适用范围**：自动接入须按[共同记录约定](../study-planner/references/coordination.md)确认为成套资料的系统课程或已有课程记录；实验操作、实验报告、风险评估、实验数据与零散问题不自动建课。明确点名本 Skill 时完成指定讲解，不强行启动其余模块。
2. **可见目录与资料先行**：严禁在 `.codex/`、`.agents/`、Worktree 或 Skill 目录创建/整理课程。首次启动须先按[材料分类](references/materials.md)与[课程文件入口](../study-planner/references/course-files.md)将本次指定全部原资料移入可见 `<course-home>/资料/`、建索引与 `inbox/` 并核验后开讲；后续仅处理明确新增批次，不在普通续学全量扫描。
3. **接续上下文**：持续课程读 `course.md`、`current.md`、当前有效计划与本课相关材料，不据工作目录推定课程；已知基础和偏好直接沿用，**不设强制入学测试**。收到讲法反馈或偏好变更读[偏好更新与教学适配](../study-planner/references/preferences.md)；临时入口仅写 `side-notes/`，保留主课断点。
4. **独立降级**：若规划 Skill 不可用，仍完成当前明确讲解并保存最少充分笔记，说明计划尚未接续，不虚构已调用其他模块。

## 备课、讲授与局部修复

1. **按需细读与诚实核对**：整门课保留粗路线，当前主题细读原文、公式、图示与批注；语音识别字幕按[课堂字幕](references/transcripts.md)处理。遇到疑点或原页不可读时按[核对与降级规则](references/source-checks.md)区分抽取、呈现与内容，不将疑点保存成已确认错误。
2. **教学完整性与图像**：核对本课概念关系、条件符号、关键推导、必要图示与示范应用；按[教学图像规则](references/teaching-visuals.md)在首次借图理解处提供并核验图像，不让几何/函数/路径只剩公式。在笔记中将重要来源页/小节对应到实质讲解位置，不用标题列表证明覆盖完整。
3. **考试补强对齐**：收到考试补强要求时按[考试依据交接](../study-planner/references/exam-handoff.md)落实到实质讲解与示范并返回位置与缺口；不把授课缩成题频清单，不以题频取消必学内容。
4. **连贯讲授**：围绕主线展开，交代问题来源、概念连接、关键推理与条件应用；按基础分段并说明衔接。课堂检查少量、简短、可跳过，长练习留课后；不自问自答并宣称学生已理解。
5. **打断与局部修复**：按[局部修复与回访交接](references/teaching-repair.md)的 4 层诊断顺序定位卡点（先修操作 → 概念条件 → 学科意义 → 表示转换），最小修复后明确回到原课断点，不重播整课；跨课重排交给规划。用户明确要求完整解析时直接提供并记录已见答案。

## 核验、保存与交接

1. **数学与图像核验**：含数学的已保存课堂记录或回复草稿运行 `python3 <course-study>/scripts/check_math.py <文件>`，结合上下文处理警告（不自动盲替原式）；教学图须按共享规则核对关系与实际画面，工具失败时保留完整讲解并标明待补图。
2. **交付与记录边界**：沿用主流程 `run ID`（独立交付时先跑 `course_delivery.py begin`），在 `lessons/`（或临时 `side-notes/`）保存概念、条件、关键推导、例子、来源、教学图参数/核验范围、未解项与教学经验观察（按[个人经验规则](../study-planner/references/teaching-experience.md)），并交由 `study-notes` 累积章笔记、由规划刷新索引并运行 `finish` 核验。
3. **诚实状态**：严格区分讲过、示范、提示后完成、独立完成与隔时保持；写入成功才说已保存，失败时提供可复制检查点。
