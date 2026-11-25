# 课程资料与可核验交付

首次系统课程、明确新增资料、资料核查和正式课程产出时使用；普通续学不全量扫描资料。这里管理文件与本轮交付，不建立第二份学习计划；课程适用范围先看[启动边界](coordination.md)。

## 可见课程目录

新课程必须先确认用户能在 Finder 直接找到的可见 `course-home`。**新建课程的原资料、课程记录与学生产出严禁存放在 `.codex/`、`.agents/`、`CODEX_HOME`、Worktree 或 Skill 目录中**（`course_delivery.py`、`course_files.py`、`course_records.py` 均会在初始化/写入前拦截）。若当前位于 `.codex/` 下且未拿到可见路径，先停下向用户确认路径（并提醒使用 Codex Local 模式）；**已建成的历史旧课**（包括经由可见软链接指向 `.codex` 历史记录，或尚未建立 `materials.json`、沿用只读原资料的旧课）允许直接沿原路径完成 `begin → finish` 续课与记录更新，不强制现场迁移或补建假清单，迁移须另行确认。

```text
<可见course-home>/
  资料/
    inbox/          后续新增资料的固定入口
    syllabus/       课程要求
    lectures/       讲义、课件、板书与批注
    transcripts/    原始课堂字幕
    exercises/      老师习题
    solutions/      老师答案与评分说明
    exams/          真题与mock
    revision/       复习讲义、公式表
    textbooks/      教材及摘录
    supplements/    已确认的其他补充材料
    unclassified/   已归档但用途待确认
  学习产出/         默认课程记录根，保留原角色/子目录
    index.html
    index.md
    materials.json
    materials-index.md
    notes/、questions/、exam/等
```

首次告诉用户实际课程目录、资料区、学习产出和inbox的绝对路径。已有课程先读实际路径与历史，不能盲目用新目录替换；全局Skill升级不自动迁移旧课。后来对某门课实际迁移时核对来源、历史和授权，保留稳定ID、原课堂/练习事实及用户修改。

## 交付执行与收尾

主流程对正式课程任务实际调用 `scripts/course_delivery.py`，专业模块沿用同一run ID；独立承担正式交付的模块也采用本流程。内部request由主流程依据本次用户任务准备，不要求学生填表。先声明本轮必须完成的资料与产物，不能等失败后删掉要求来制造通过。

```text
python3 <study-planner>/scripts/course_delivery.py begin --course-home <可见课程目录> --root <课程记录根> --activity <setup|intake|lesson|analysis|practice|notes> --request-json <本轮内部交付要求.json>
python3 <study-planner>/scripts/course_delivery.py finish --root <课程记录根> --run <begin返回的run ID>
```

begin只记录本轮要求与相关文件原版本，不扫描无关资料。按对应模块保存实质内容后运行finish，由它核对并刷新索引和可见课程入口；同一run中不要再单独重建索引，以免版本混用。它核对本轮声明的真实文件、哈希及入口链接，不把旧文件存在、空目录或“已安排”当作本轮交付。缺项先由原职责补做再finish；仍有缺项就明确未完成，保留已完成教学和历史断点。笔记仍按已讲范围更新所属章节，不为过检查补造完整章节或学生回答。


内部request示例（模块准备，学生无需填写）：

```json
{"sources":["/绝对路径/本次给出的课程资料"],"expected":[{"path":"lessons/L01.md","kind":"lesson","freshness":"new"},{"path":"notes/chapters/C01.html","kind":"notes","freshness":"new"}]}
```

`setup`首次资料默认取已明确的course-home，自动要求course/materials/course-map/study-plan/current五份实际课程记录；`intake`未给sources时只取固定inbox本批文件。普通lesson/notes/analysis/practice不传sources，不清点整门课。`expected`列本次应交付的相对路径、kind与freshness：new/changed不能用旧文件充数；reuse只接受既往真实核验回执且来源版本一致的产物。按任务使用lesson、notes、prompt、solution、analysis_brief、analysis_detail、review等kind；material_ids只填本轮相关资料ID。lesson要求实质课堂与本章笔记，practice要求题干和作者解析，并核对实际检查点；analysis要求内部依据与可见简报。若用户只是临时答疑或尚未完成一课，选对应aside任务、保存真实断点，不伪造已完成章节。

资料移动分类完毕后，先执行下面的资料交接核对，再交给相关教学/分析模块；它只核对本批资料，并实际生成可读的materials-index.md类型/章节索引与资料入口，不要求教学产物提前存在。资料核验返回required_handoffs：本批有习题/tutorial、mock、试卷或答案评分说明时，需交exam-analysis保存该批已读范围的brief及内部依据；没有考试日期也适用，但不要求读完全部试卷。最终finish仍检查整个本轮交付。

```text
python3 <study-planner>/scripts/course_delivery.py verify --root <课程记录根> --run <本轮run ID> --materials-only
```

finish依据本次检查写delivery.md/delivery.json成功或失败回执；成功时生成course-home中的课程入口.html，给出总入口、inbox和真实产物链接。失败返回非零与漏项，保留失败回执，补做后对同一run重新finish。回执文件检查不代替逐式内容和显示核对。

该入口被调用后才有可核验结果；Skill文字、检查器或成功回执不能强迫任意聊天自行调用它。未实际运行不得声称检查通过。验证文件交付不证明数学正确、来源理解正确或学生掌握；教学内容、图像与实际渲染仍按各模块核对。流程评估应查看普通自然语言请求下的实际工具轨迹与文件结果，不只查规则是否存在。

## 首次指定资料全部整理后再教学

首次先列出用户本次指定全部原始文件与资料目录；只清点这些来源，不扩大到下载目录、主目录或其他课程。使用 `scripts/course_files.py` 初始化资料清单，并移动本批资料到资料区、登记类型和章节索引、建固定inbox；完成该批结果核验后再交给教学、考试分析或题目模块。这里的“全部”是当前已提供批次，不是整学期必须上传齐全，也不是首讲前读完全部正文。

```text
python3 <study-planner>/scripts/course_files.py init --root <课程记录根> --materials-root <可见course-home/资料> --course <课程ID> --source-root <本次指定原资料目录>
python3 <study-planner>/scripts/course_files.py scan --root <课程记录根>
```

begin已返回本批文件路径和SHA时直接复用，不再重复scan。scan仅用于明确的全量核查或独立初始清点，比较文件哈希并报告新增、改动、缺失、可能移位、重复和无法读取项；不代表正文已读。普通“继续学习”不运行这个全量命令。教师整理时抽样正文、目录和必要原页判断类型、版本与章节；低把握文件也移入unclassified并明确待确认，不忽略、不捏造分类。

每份文件归一个主要类型；题答同册只存一份，以用途标签区分。章节以资料ID和页/小节/时间戳关联，不按章复制。模块内部准备条目JSON：

```json
{"path":"/绝对路径/新讲义.pdf","sha256":"<本次检查得到的64位SHA256>","category":"lectures","chapters":[{"chapter":"C01","locator":"第3–8页"}],"inspection":"第1页与目录抽样，C01相关页待读","uses":["教学主线"]}
```

已有条目更正携带原id。定位不明可留空chapters并登记待定位，不猜页码；inspection区分登记、抽样和细读。

```text
python3 <study-planner>/scripts/course_records.py read --root <课程记录根> --path materials.json
# 多份资料推荐一次批量导入（支持 --items-json - 从 stdin 读取 JSON 数组，内部已做整批预检与逐份移动）：
python3 <study-planner>/scripts/course_files.py import-batch --root <课程记录根> --items-json - --expected <materials.json的原SHA>
# 单份资料补充或重新分类时也可单独调用：
python3 <study-planner>/scripts/course_files.py import --root <课程记录根> --item-json <单份文件条目.json> --expected <materials.json的原SHA>
```

import默认执行已授权的移动，外部来源不再一律复制。完成后原位置不留同内容副本；重新分类移动同一规范文件。相同内容复用既有规范文件，同名异内容保留真正不同的版本，不覆盖。每次用返回的新清单SHA继续，来源变化或旧SHA冲突先核对合并。只有用户明确保留只读来源时使用 `--copy`；确实无法移动则报告实际限制和未移动项，不能静默复制后声称已转移。

移动过程中保留原始字节及来源、版本信息，使用恢复journal协调目标文件、登记和源移除。中断或核验失败保留可恢复字节，运行course_files.py move-recover --root <课程记录根> --decision finish或abort明确恢复后回读；不能手删journal绕过未完成状态，也不能只因目标已出现就宣称成功。

`import-batch` 会在改任何文件前对整批条目做完整干跑预检（检查 `id`、SHA、来源根、目标冲突与重分类边界），任一项预检失败则零文件改动。若执行阶段发生磁盘/中断故障或批内检测到 `materials.json` 手工修改冲突，**脚本绝不静默回滚覆写已提交条目或手工修改**，而是输出包含 `completed`、`failed_item`、`remaining_items`、`pending_move_recovery` 与 `last_committed_registry_sha256` 的结构化 JSON：若 `pending_move_recovery` 为真，先运行 `move-recover`——**`--decision finish` 已经移走并登记该故障文件，后续只对 `remaining_after_finish` 重试；`--decision abort` 会恢复该文件，后续对 `remaining_after_abort`（含 `failed_item`）重试**；回读 `materials.json` 取当前 SHA 后再续跑即可。

materials.json是同一文件清单；materials-index.md是派生类型/章节索引；materials.md保留真实用途和阅读范围，不被索引覆盖。教师把关键对应写回materials/course-map。字幕按[ASR规则](../../course-study/references/transcripts.md)保留原话和定位。

## 后续新增与针对性检查

以后把新增资料放入实际 `资料/inbox/`，或在聊天中指出具体文件。前台需要处理资料时轻量列举这个固定入口，或直接使用用户给出的新增批次，然后只检查该批文件、登记及受影响产物。不自动遍历和哈希全部资料；没有后台监控。文件直接放入某个类型目录时，也可明确指出该批路径接收，无需先复制回inbox。

新附件和工具下载的资料进入同一移动流程；保留原附件路径，不扫描整个附件/下载目录。首次未覆盖的新来源先以共同助手带原SHA合并source_roots，保留原清单和未知字段，再仅处理指定批次。用户明确要求全量查漏或来源审计时才运行scan并说明范围。

新增不使旧分析全部失效。内容未变而路径改变只更新定位；实际内容改变/缺失时按资料ID、版本和原页引用检查相关分析/笔记，由原职责更正受影响部分。没有依赖证据就保留待核对，不把文件检查冒充分析复核。历史教学、作答、提示和计划历史继续保留。

## 学生产出区域与导航

以下位置相对于课程记录根；新课程默认在可见course-home的学习产出中，原角色保持：

| 位置 | 用户查找什么 | 维护者 |
| --- | --- | --- |
| index.html、index.md | 可点击总入口、资料入口和未生成状态 | 规划 |
| materials-index.md | 同一资料的类型与章节定位 | 规划派生 |
| lessons/ | 实质课堂原记录 | 教师/主流程 |
| notes/（主要chapters/；lessons/可选；exports/按需） | 完整章笔记、完成课程后的整课整理与按需PDF | 笔记模块 |
| questions/prompts/、questions/solutions/ | 对应稳定ID的题干与作者解析 | 题目模块 |
| practice/ | 实际作答、帮助与反馈 | 规划 |
| reviews/ | 已做题或已展示解析的阅读集 | 规划 |
| exam/brief.md | 实际范围、知识点、题型、能力和缺口的简报 | 分析模块，与证据同批更新 |
| exam/其余记录 | 内部逐题标注、能力链、统计及核对依据 | 分析模块 |
| transcripts/ | 字幕理解、疑点及原始定位 | 教师/主流程 |

章笔记沿用v3连贯完整正文及精简/回忆视图，按课反馈积累，不退回最终公式清单或为每课强建独立笔记。notes角色只维护notes，计划/证据留原维护者。内部详细分析也在该课程目录，不写进全局Skill代码目录。

总览只直接链接真实exam/brief.md；未知含答案的旧questions合并记录和未展示作者解析不进入题干入口。作者解析按实际反馈/明确请求开放，文件生成不等于学生已看过。旧课堂、题目路径不批量改名或复制成第二套学习档案。

活跃run由finish刷新总入口。以下命令仅供没有活跃交付任务的单独导航维护：

```text
python3 <study-planner>/scripts/course_records.py read-set --root <课程记录根> --paths materials.json index.md index.html materials-index.md
python3 <study-planner>/scripts/course_files.py index --root <课程记录根> --expected-manifest <materials.json的SHA> --expected-targets-json <三个入口目标SHA的内部JSON>
```

目标JSON为 `{"index.md":"absent或原SHA","index.html":"absent或原SHA","materials-index.md":"absent或原SHA"}`。保留用户修改，冲突先回读合并；不能换上新SHA后覆盖未经合并的批注。手工索引也须遵循共同写入保护。只有用户明确索要全部作者解析时才用 `--show-solutions`，它不能表示仅开放某一道题。

交付回复给出真正移动数、去重/待确认/未移动项和影响范围，附inbox绝对路径链接、本轮可见笔记、题干、分析简报及总入口链接。未发生的任务不凑产物；已声明但缺少的产物明确未完成，先补做再复查。尚未生成的栏目可以显示状态，不能用空文件或空目录冒充交付。

登记损坏时停止覆盖并指出位置，保留原字节和备份；不得重置清单或静默丢条目。共同记录写入器只核验角色、语法与版本；文件交付检查不能代替语义和内容核对。

参考方法：[Superpowers交付前验证](https://github.com/obra/superpowers/blob/main/skills/verification-before-completion/SKILL.md)强调以刚执行的证据支撑完成声明；[Anthropic长任务harness](https://www.anthropic.com/research/effective-harnesses-for-long-running-agents)区分首次初始化与增量工作。本流程采用相应方法，不引入这些项目作为运行依赖，也不以其测试代替本课程验收。
