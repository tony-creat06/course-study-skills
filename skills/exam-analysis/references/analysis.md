# 分析数据与统计

先阅读原题，再填结构化数据。此脚本解决可重复计数，不替代语义理解、视觉核对或考试预测。

输入JSON的`papers`为列表。每卷含`id`、`exam_year`（实际考试年，可null）、`kind`（real/mock/practice）、`source`（路径与版本说明）、`scope_complete`（是否已完成所声明全卷范围的分析）、`all_questions_required`（true/false/null）和`questions`。每大题含`number`、`primary_topic`（未知null）、`parts`；每小问含`label`、`marks`（未知null）、`topics`（实际所测能力对应的主题）、`source_page`（从1开始的PDF页码，可null）；可加`abilities`能力列表与题干、命令动词等字段。题干/解析可保存在同记录的额外字段，不丢弃原意、图示位置或父题条件。

```text
python3 <study-planner>/scripts/course_records.py read-set --root <课程目录> --paths exam/items.json exam/profile.md exam/summary.json
python3 <exam-analysis>/scripts/summarize_exam.py --input <课程外暂存的新题目记录.json> --output <课程外暂存的新统计.json>
python3 <study-planner>/scripts/course_records.py bundle --root <课程目录> --role analyst --body-file <关联分析更新.json>
```

先保留read-set返回的原SHA，在课程外准备完整题目记录、对应profile及生成的统计，核对后以 `{"updates":[{"path":"exam/items.json","expected":"<原SHA或absent>","content":"<完整新JSON正文>"}, ...]}` 整批提交三个关联结果。JSON正文由JSON编码器编码，不能手工把未转义换行拼进字符串。沿用已有实际文件名；不为示例强行建空文件。旧SHA冲突时重新读取并合并，再计算统计，不能只替换expected。成功后read-set回读，返回各文件SHA和真实分析范围。

`summarize_exam.py --root/--path/--expected` 保留单个统计文件的版本保护供旧调用使用；它不同时发布原题记录和profile。本次更新涉及关联文件时使用上述暂存计算及analyst批次，不能以几个单文件成功写入代替整批发布。

输出包括按年/卷的主要主题计数、每大题每主题去重的覆盖、已知小问分值及联合考点分值、未知分值和未分类题。覆盖分母是大题数，可重叠；主主题分布包含未分类项。所有可见题目的分值不自动等于一名考生必须作答的分值，尤其是选答试卷；仅在全卷分析完成、没有未知分值且提供`expected_available_marks`（全卷可见题目分值）时核对总分；这不同于选答时的考生必答分值。近期优先是用户的使用规则，不偷偷加成未经解释的概率。

相同paper ID或题号发生重复时脚本报错，要求核对重复来源后再决定合并，不静默吞掉矛盾资料。分值为null保留未知，不能当0；联合主题没有拆分依据时保留一个联合组，不能给每个标签重复记满分。

小问可用 `abilities`、`styles`、`command_verbs` 三个字符串列表记录实际能力、题型和命令动词；标签按课程语义统一，未能分类用空列表，不根据动词自动猜能力。脚本在 `assessment_dimensions` 中分别汇总大题去重覆盖与联合分值组，保留小问/页码，列出未分类小问。联合组占比只以本卷当前已分析的已知可见分值为分母；各维度分别描述同一批分值，不能跨维度相加，也不能把联合组占比拆成单个能力权重。旧输入可读，但缺失的新字段保持未分类，不能宣称已分析风格。

统计加上原题能力链和题设要求，按[考试依据交接](../../study-planner/references/exam-handoff.md)交给规划，由规划比较已有教学与实际作答后安排补强。统计本身不维护个人优先级或计划。

去重计数模式参考[past-paper-topic-analyzer的build_freq_year](https://github.com/GeniusTrader-Harry/past-paper-topic-analyzer/blob/main/scripts/build_xlsx.py)；解析与展示分离、父题/小问结构参考其[parse_essays.py](https://github.com/GeniusTrader-Harry/past-paper-topic-analyzer/blob/main/scripts/parse_essays.py)。本脚本按本项目结构独立实现，未采用经济学专用正则。来源与具体取舍记录在项目research/reference-adoption-map.md。

结构化题目JSON及关联分析通过共同记录脚本的analyst批次保存，经过版本比较、锁、备份与中断恢复。--output只用于课程外临时计算，不直接覆盖共享分析。分值/分类完整不代表原题读法已核实；材料疑点按共同核对规则处理。
