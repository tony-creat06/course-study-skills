# 分析数据与统计

先阅读原题，再填结构化数据。此脚本解决可重复计数，不替代语义理解、视觉核对或考试预测。

输入JSON的`papers`为列表。每卷含`id`、`exam_year`（实际考试年，可null）、`kind`（real/mock/practice）、`source`（路径与版本说明）、`scope_complete`（是否已完成所声明全卷范围的分析）、`all_questions_required`（true/false/null）和`questions`。每大题含`number`、`primary_topic`（未知null）、`parts`；每小问含`label`、`marks`（未知null）、`topics`（实际所测能力对应的主题）、`source_page`（从1开始的PDF页码，可null）；可加`abilities`能力列表与题干、命令动词等字段。题干/解析可保存在同记录的额外字段，不丢弃原意、图示位置或父题条件。

```text
python3 <study-planner>/scripts/course_records.py read-set --root <课程目录> --paths exam/items.json exam/profile.md exam/summary.json exam/brief.md
python3 <exam-analysis>/scripts/summarize_exam.py --input <课程外暂存的新题目记录.json> --output <课程外暂存的新统计.json>
python3 <study-planner>/scripts/course_records.py bundle --root <课程目录> --role analyst --body-file <关联分析更新.json>
```

先保留read-set返回的原SHA，在课程外准备完整题目记录、对应profile、生成的统计及同一范围的brief，核对后以 `{"updates":[{"path":"exam/items.json","expected":"<原SHA或absent>","content":"<完整新JSON正文>"}, ...]}` 整批提交四个关联结果。JSON正文由JSON编码器编码，不能手工把未转义换行拼进字符串。沿用已有实际文件名；不为示例强行建空文件。旧SHA冲突时重新读取并合并，再计算统计，不能只替换expected。成功后read-set回读，返回各文件SHA和真实分析范围。已有旧分析仅补简报时，把未变的相关内部记录及其原SHA一同纳入批次核对，正文不重写；旧三文件数据集继续可用，不为凑四份创建空证据。简报与内部证据同一批发布，避免新统计配旧简报；失败保留待提交正文，不声称简报已更新。

`summarize_exam.py --root/--path/--expected` 保留单个统计文件的版本保护供旧调用使用；它不同时发布原题记录和profile。本次更新涉及关联文件时使用上述暂存计算及analyst批次，不能以几个单文件成功写入代替整批发布。

输出包括按年/卷的主要主题计数、每大题每主题去重的覆盖、已知小问分值及联合考点分值、未知分值和未分类题。覆盖分母是大题数，可重叠；主主题分布包含未分类项。所有可见题目的分值不自动等于一名考生必须作答的分值，尤其是选答试卷；仅在全卷分析完成、没有未知分值且提供`expected_available_marks`（全卷可见题目分值）时核对总分；这不同于选答时的考生必答分值。近期优先是用户的使用规则，不偷偷加成未经解释的概率。

相同paper ID或题号发生重复时脚本报错，要求核对重复来源后再决定合并，不静默吞掉矛盾资料。分值为null保留未知，不能当0；联合主题没有拆分依据时保留一个联合组，不能给每个标签重复记满分。

小问可用 `abilities`、`styles`、`command_verbs` 三个字符串列表记录实际能力、题型和命令动词；标签按课程语义统一，英文命令动词先统一大小写，保留原题措辞在原文/来源字段，避免同一动词被拆成多个统计标签。统计后回到原小问核对各标签对应的大题集合与联合分值，不能只检查总计100%。未能分类用空列表，不根据动词自动猜能力。脚本在 `assessment_dimensions` 中分别汇总大题去重覆盖与联合分值组，保留小问/页码，列出未分类小问。联合组占比只以本卷当前已分析的已知可见分值为分母；各维度分别描述同一批分值，不能跨维度相加，也不能把联合组占比拆成单个能力权重。旧输入可读，但缺失的新字段保持未分类，不能宣称已分析风格。

统计加上原题能力链和题设要求，按[考试依据交接](../../study-planner/references/exam-handoff.md)交给规划，由规划比较已有教学与实际作答后安排补强。统计本身不维护个人优先级或计划。

去重计数模式参考[past-paper-topic-analyzer的build_freq_year](https://github.com/GeniusTrader-Harry/past-paper-topic-analyzer/blob/main/scripts/build_xlsx.py)；解析与展示分离、父题/小问结构参考其[parse_essays.py](https://github.com/GeniusTrader-Harry/past-paper-topic-analyzer/blob/main/scripts/parse_essays.py)。本脚本按本项目结构独立实现，未采用经济学专用正则。

结构化题目JSON及关联分析通过共同记录脚本的analyst批次保存，经过版本比较、锁、备份与中断恢复。--output只新建课程外临时.json文件；已有目标或其他后缀拒绝写入，重试选新文件名，不直接覆盖共享分析。分值/分类完整不代表原题读法已核实；材料疑点按共同核对规则处理。

## 面向学生的分析简报

每次分析首次交付或实质更新，同时准备 `exam/brief.md`，通常用一页左右的中文说明或紧凑表格表达，内容多少按证据决定。它是内部分析的阅读摘要，不是另一份计划，也不能取代内部原题记录供教学与出题引用。

- 分析范围和适用版本：课程/学年、实际查看的卷/年份、正式卷与mock/习题的区别、已分析题号或页码、是否仅局部分析。
- 主要知识点与题目形式：实际出现的主题、命令动词、计算/推导/解释/作图等要求；给少量原卷定位，不复制完整题库。
- 考查能力与解题要求：需要选择什么方法、解释什么条件、怎样连接步骤；可提供有依据的学习关注点，不能宣称规划已采纳或学生已经掌握。
- 数量依据与局限：只在已核对范围内给出题数/分值/频次，写明分母、联合考点及选答影响；未知留未知，少量试卷不编造趋势或“必考”。
- 缺口和更新：未读卷页、未确认版本、缺失评分说明及需补资料；注明分析日期/版本和实际源范围。

详细逐题标注、能力链、统计JSON和审查过程留在同一课程工作区的 `exam/items.json`、`exam/profile.md`、`exam/summary.json` 等既有内部记录；个人课程资料不能放进通用Skill源码或全局安装目录。学生产出入口只链接 `exam/brief.md`，详细文件按明确请求提供。没有真实分析时不虚构简报结果。

在同一analyst批次准备brief和相关新证据，保留对应源快照信息供后续追溯；学生正文不必堆放长SHA或内部协议。简报不泄露尚未展示的未来练习解析；从往年题抽象题型和能力，不直接复制私有作者解答。资料改动只更新受影响内容和这份对应简报，未变化部分复用；详细记录与简报不一致时先核对，不能让简报覆盖真实证据。
