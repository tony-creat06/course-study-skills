# 分析数据与统计

先阅读原题，再填结构化数据。此脚本解决可重复计数，不替代语义理解、视觉核对或考试预测。

输入JSON的`papers`为列表。每卷含`id`、`exam_year`（实际考试年，可null）、`kind`（real/mock/practice）、`source`（路径与版本说明）、`scope_complete`（是否已完成所声明全卷范围的分析）、`all_questions_required`（true/false/null）和`questions`。每大题含`number`、`primary_topic`（未知null）、`parts`；每小问含`label`、`marks`（未知null）、`topics`（实际所测能力对应的主题）、`source_page`（从1开始的PDF页码，可null）；可加`abilities`能力列表与题干、命令动词等字段。题干/解析可保存在同记录的额外字段，不丢弃原意、图示位置或父题条件。

```text
python3 <study-planner>/scripts/course_records.py read --root <课程目录> --path exam/summary.json
python3 <exam-analysis>/scripts/summarize_exam.py --input <题目记录.json> --root <课程目录> --path exam/summary.json --expected <上一步sha256或absent>
```

输出包括按年/卷的主要主题计数、每大题每主题去重的覆盖、已知小问分值及联合考点分值、未知分值和未分类题。覆盖分母是大题数，可重叠；主主题分布包含未分类项。所有可见题目的分值不自动等于一名考生必须作答的分值，尤其是选答试卷；仅在全卷分析完成、没有未知分值且提供`expected_available_marks`（全卷可见题目分值）时核对总分；这不同于选答时的考生必答分值。近期优先是用户的使用规则，不偷偷加成未经解释的概率。

相同paper ID或题号发生重复时脚本报错，要求核对重复来源后再决定合并，不静默吞掉矛盾资料。分值为null保留未知，不能当0；联合主题没有拆分依据时保留一个联合组，不能给每个标签重复记满分。

去重计数模式参考[past-paper-topic-analyzer的build_freq_year](https://github.com/GeniusTrader-Harry/past-paper-topic-analyzer/blob/main/scripts/build_xlsx.py)；解析与展示分离、父题/小问结构参考其[parse_essays.py](https://github.com/GeniusTrader-Harry/past-paper-topic-analyzer/blob/main/scripts/parse_essays.py)。本脚本按本项目结构独立实现，未采用经济学专用正则。来源与具体取舍记录在项目research/reference-adoption-map.md。

结构化题目JSON通过共同记录脚本的analyst角色保存；上述汇总模式也经过版本比较、锁与备份。--output只用于课程外临时计算，不直接覆盖共享分析。分值/分类完整不代表原题读法已核实；材料疑点按共同核对规则处理。
