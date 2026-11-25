---
name: study-notes
description: Compile complete, personalized chapter lecture notes from saved systematic-course feedback into desktop-first offline HTML, with concise and recall views, bilingual terminology and optional PDF. Use after lessons or chapters in an established course, or on explicit invocation; isolated explanations and lab/report work do not implicitly activate this suite.
---

# 学习笔记

接收其他四模块已保存的反馈，随学习进度按章组织可连续阅读的个性化离线 lecture notes（中文讲清联系，保留英文术语及必要英文答题表述）。**不要求学生填写输入表、重交材料或接受笔记采访。**

## 边界与接收

1. **启用与路径**：仅用于系统课程已保存反馈或明确点名范围，严禁在 `.codex/` 等隐藏目录建笔记。遵循[共同记录约定](../study-planner/references/coordination.md)与[反馈交接](references/handoff.md)，沿用规划确认的学习者、可见课程根、已讲范围与课/章/课程结束信号；首次开课须先由主流程完成资料移动归档与索引。
2. **角色与只读边界**：仅用 `notes` 角色写 `notes/`；不修改计划、检查点、课堂、考试、题目或作答记录。发现原记录或来源错误交回原维护者更正后重建，不自行编造未学内容或替学生建立掌握状态；临时答疑待规划采用后再纳入。
3. **按需复用**：无新考试/题目反馈时直接复用有效记录，无相关内容则省略该栏目，不必每次重跑四模块。

## 按章积累与内容编排

1. **章为主单元**：每课反馈合入所属章节同一份连贯正文（课级临时笔记仅按需保留）；章节未完须标明已讲边界，仅由规划确认章结束后称本章完整；整门课完成后再依据真实范围与反馈另编全课程综合整理（不简单拼接章文件）。
2. **编排与三视图**：生成前先读[笔记生成与表达](references/note-writing.md)，使用 v3 章节结构与覆盖映射：
   - **完整视图**：默认直接展开全部核心正文（定义、必要先修、推导起点与理由、中间式、符号条件、已展示例子与复用已核验教学图），只将补充推导/长旁注折叠。
   - **精简视图**：保留问题、起点、方法选择、成立条件与结论用途，不退化成孤立公式清单。
   - **回忆视图**：按需提供起点/方法提示与可回查答案；点击回忆不记作作答或掌握。题目模块未展示的作者解析严禁写入笔记。
3. **检索与速查**：按需建立中英文术语/符号速查与关键公式编号（仅选高频回查项），正文须自足并内嵌离线正文检索。

## 渲染、核验与交付

1. **离线网页与版本锁**：按[离线网页与PDF](references/offline-notes.md)渲染单文件离线 HTML（桌面阅读为主，可选辅助窄屏适配与完整 PDF 导出；LaTeX 源码不直接暴露给学生）。沿用稳定课/章 ID，写入时核对来源 SHA 与目标旧 SHA，合并保留用户手改；沿用主流程 `run ID`（独立正式整理先运行 `course_delivery.py begin`）。
2. **交付前复核**：对照原反馈逐项核对主线、条件、符号、推理与来源；检查教学图图文一致及桌面渲染、视图切换、折叠、检索与离线效果（导出 PDF 时核对分页与公式）。返回笔记路径、已整理范围、来源版本、缺项/疑点与实际验证范围，交规划刷新索引并运行 `finish`。生成失败时保留课堂完成事实与断点。
