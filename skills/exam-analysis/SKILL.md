---
name: exam-analysis
description: Analyze past papers, marking schemes and current requirements into traceable exam coverage, question styles and topic statistics. Use within an established systematic course or when explicitly invoked; isolated lab/report tasks do not implicitly activate this course suite. Do not create the study schedule.
---

# 考试要求与历年卷分析

产出规划、教师与出题可共用的可追溯考试依据，保留来源、统计口径与适用边界；**不维护第二套学习计划、不修改课堂进度或学生掌握记录。**

## 边界与范围核验

1. **启用与路径**：遵循[共同记录约定](../study-planner/references/coordination.md)的系统课程范围；明确点名本 Skill 时可单独分析指定试卷。新课须先由主流程完成资料移动归档与索引后再进入分析；资料变化时只刷新受影响部分，普通续学不重扫全课。输出写入可见课程根下 `exam/`（`analyst` 角色），严禁写入 `.codex/` 或全局 Skill 目录。
2. **核对现行要求**：沿用已知课程身份、学年与考核形式；分别记录封面日期、适用学年与文件名，明确区分正式真题、mock、练习卷与老师 revision/公式表/评分说明，不把旧卷自动当成现行要求，也不用近期未考排除必学内容。缺关键信息从材料核对，确实无法判断才问一个问题。

## 逐题理解与统计规范

1. **真实阅读与疑点规则**：按年逐题核对题干条件、小问依赖、公式图示与分值；文字抽取不足时查看原页，区分“登记范围”与“全文已审阅”。公式/版本存疑或原页不可读时按[共同核对规则](../course-study/references/source-checks.md)处理，不替乱码修出未经确认的版本。
2. **优先顺序与去重统计**：近期两三年真题定风格，老师习题定课程重点，更早真题作次要参考；资料极少时诚实说明证据范围，不编造趋势或押题概率。按[分析数据与统计](references/analysis.md)保留结构化题目 JSON、`exam/profile.md` 与面向学生的 `exam/brief.md`：
   - 宏观分布按大题主要主题去重，小问覆盖可重叠但分值不重复分配，联合考点保留联合分值。
   - 写清统计单位、分母、已分析范围、未分类项与选答结构影响；`scripts/summarize_exam.py` **只对已理解并标注的 JSON 计数**，不自动读 PDF 或判题意，运行后须核对题数/分值并保留未分类项。

## 原子发布与跨模块交接

1. **批次原子发布**：在课程外准备关联的题目记录、profile、统计与 `exam/brief.md`，用 `course_records.py bundle --role analyst` 整批提交到 `exam/`，再用 `read-set` 回读同一版本交付；禁止逐个覆盖后宣称整份分析已发布。`brief.md` 只概括已分析范围、题型、能力与缺口，不剧透未展示完整答案或内部审查细节。
2. **交付与复用**：沿用主流程 `run ID`（独立正式分析先跑 `course_delivery.py begin`），完成后交规划刷新入口并运行 `finish`；无新资料或范围变化时直接复用已有有效分析。按[考试依据交接](../study-planner/references/exam-handoff.md)向规划/教学/出题交付带范围的分值线索、能力链例证与 `state/define/explain` 参考表达，供 `study-notes` 按真实范围采纳。
