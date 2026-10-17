# 共同课程记录与双对话交接

五个Skill协作和写记录时读取本页；这是同一份运行约定。课程内容留在课程文件夹，Skill分发包不包含个人资料。Markdown可直接供Obsidian打开，不依赖插件。

## 适用范围与启动

本组用于以成套课程资料为依据的持续、系统课程教学。自动启用前确认用户正开展这种学习，且已有可识别的课程范围和可用教学主线，或已有对应系统课程记录。成套不等于整学期材料已全部上传；逐周提供讲义和字幕可正常接续。单凭课程名、一个PDF或学习词汇不启动全组。

实验操作、仪器说明、风险评估、实验数据处理与实验报告默认按当前任务处理，不自动建立课程计划和学习记录；已有理论课程记录也不把另一个实验任务变成续学。零散概念/题目请求直接回答；已建立系统课程内的临时答疑可按原side-notes入口。用户明确点名一个Skill时完成其指定职责，不因使用一个模块就调用五个模块或强建系统课程。用户明确要系统学习实验课程的理论大纲时，按该明确目标判断。

## 身份与存放

确认当前课程记录归属的学习者；同一课程的不同学习者使用各自记录根目录。已有归属明确的记录直接接续，不每课重复询问身份；归属不清且会混用个人记录时先确认。

依据用户明确课程、材料正文和已有记录确认身份。指定一个与原始材料分开的课程记录根目录，并告知用户；已有目录沿用。先遵循实际适用的工作区与项目规则。新建独立课程项目时，先完成该环境要求的项目初始化、目录确认和存放说明；Skill不能提供豁免。继续已有课程或在其目录增加普通记录不等于新项目，不重复启动项目初始化。已有课程优先沿用记录根目录；新项目获确认后可用`<项目>/outputs/courses/<已确认课程ID>/`，不写原始材料目录或因概念问题自建另一份课程。无法确认同一课程路径时问一个必要问题，不能在两个对话各创建一份课程。

| 记录 | 内容/维护者 |
| --- | --- |
| `course.md` | 身份、目标、基础自述、时间/日期、有效偏好与个人教学策略及其来源/范围、原始材料路径；主对话维护共同事实 |
| `materials.json`、`materials-index.md` | 字节校验、类型归档与章节定位索引；教师判断用途，主流程用文件助手登记和派生 |
| `index.md`、`index.html` | 实际资料与产出入口；规划派生维护，不存第二套进度 |
| `materials.md`、`course-map.md` | 材料用途/实际阅读范围、内容与先修关系；教师维护，不是第二份日程 |
| `study-plan.md` | 唯一有效执行计划、当前模式、依据与调整理由；主对话规划维护 |
| `current.md` | 实际讲到的位置、未解项、下一步及来源、返回点、已处理答疑ID；主对话维护 |
| `lessons/`、`practice/` | 可复习的课堂笔记、实际作答/提示与反馈；主对话维护 |
| `side-notes/` | 临时概念/指定题目、实际作答/提示、未解项；答疑入口每次独立记录 |
| `exam/` | 分析模块维护详细考试/题目工作记录，以及面向学生的brief.md简报；产出入口只链接简报 |
| `questions/` | 原题/变式/新题、完整解析、核对范围；题目模块维护；新文件分prompts/与solutions/，旧路径保留 |
| `transcripts/` | 字幕派生读法与纠正疑点；教师/主流程维护，原始字幕留资料目录 |
| `reviews/` | 已做题HTML阅读输出；规划汇编，不作为另一份学习状态 |
| `notes/` | 从四模块反馈派生的章节正文、课程整理HTML及内部JSON；笔记模块维护，不承载计划或掌握状态 |

资料与产出按[课程文件工作流](course-files.md)组织：首次建立/旧课程下次接续说明实际inbox、归档及记录绝对路径；每次接续扫描新增/变化，保存后刷新可点击产出入口。原资料按类型归档并以章节索引关联；不把课程outputs当新资料反复导入。

按实际需要建立，不能先生成一堆空文件。旧原型的course/materials/current/lessons直接保留。首次接续读出已讲位置、真实证据与未解项，仅在需要时补study-plan或course-map；原课堂文件继续用原路径，不因脚本接管重命名、重播或转换成“已掌握”。旧records.md已由本共同约定接续，不需要为课程文件做批量格式迁移。

偏好沿用 `course.md` 与相关原笔记，具体更新遵循[偏好适配规则](preferences.md)。临时要求、待验证观察和当前有效偏好分清，不另建并行画像或把个人内容写入通用Skill。双入口仍按下述角色边界交接。

个人策略的复盘与下一次应用遵循[教学经验规则](teaching-experience.md)：详细经过留原笔记，有效策略留 `course.md`，待观察动作留既有检查点/计划。学习者身份和范围不能因读取了同一份Skill而合并；朋友使用同一分发包从自己的记录开始。

## 主线与临时入口

主对话组织连贯学习，规划唯一决定跨课顺序。教师在课堂内补当前必要先修、换例子或修复推理；涉及路线或时间取舍时留下证据，由规划更新正式计划。

临时入口读共同事实和必要当前上下文，直接答疑；只写 `side-notes/`，不覆盖主计划、主课进度、掌握结论或题库。发现资料/答案疑点先按[核对规则](../../course-study/references/source-checks.md)保存证据方式、当前判断与建议，未确认疑点不能成为后续规划的既定事实。学生明确变更目标/日期时记录原话要求，主对话接续时优先处理。

主对话在下次学习或自然课间自动读取新增答疑，统一判断补强，保留主课接续点。`current.md`保留已处理条目ID及处理结论：例如“未检验，只加入一次换情境练习”。没有实际主对话运行就没有后台同步，也不主动发消息或唤醒其他对话。

## 写入与恢复

优先使用本Skill的 `scripts/course_records.py`：先read取得内容和SHA，再write携带原SHA。写入会短等协作锁（默认最多2秒，可用--lock-timeout设置0–30秒）、核对旧版本、备份旧文件、原子替换；锁超时保留待保存正文并稍后回读重试；等到锁不代表拿到最新版本，旧SHA仍须匹配。旧版本不匹配时回读合并，不能强行覆盖。临时记录用note命令自动生成唯一ID。角色参数只防常见误写，不是平台权限隔离，不能绕过文件系统授权。

```text
python3 <study-planner>/scripts/course_records.py read --root <课程目录> --path current.md
python3 <study-planner>/scripts/course_records.py write --root <课程目录> --role main --path current.md --expected <上一步sha256或absent> --body-file <更新后的UTF-8文件>
python3 <study-planner>/scripts/course_records.py note --root <课程目录> --role aside --body-file <本次答疑笔记>
```

写入范围按角色和目录限定：main维护共同Markdown、materials.json、派生index.md/index.html/materials-index.md、lessons/practice的Markdown、transcripts的Markdown/JSON及reviews的JSON/HTML；analyst维护exam的Markdown/JSON；questions维护questions的Markdown/JSON；aside仅新增side-notes的Markdown；notes仅维护notes的JSON/HTML。笔记不能写共同事实、计划、断点、考试、题目或作答目录。notes不能bundle或recover，原main/analyst批次能力保持原边界；正式笔记由[笔记渲染器](../../study-notes/references/offline-notes.md)同锁核对来源和目标版本后保存。JSON写入先检查语法；语义与证据仍由模块核对。共享JSON也先read再write。汇总/HTML脚本写课程输出时使用--root/--path/--expected模式，从而保留同样版本保护；--output用于课程外临时预览，不是共享记录覆盖的捷径。

多个文件共同描述一份考试分析时，先用 `read-set` 一次取得相关原题记录、profile、统计与本次相关brief的内容/SHA，分析模块在课程外准备新正文及统计，再以 `bundle --role analyst` 整批提交到exam。不能逐个write这些关联结果后称整份分析已发布。规划采用时、教师或题目模块自行读取当前考试依据时，同样用read-set读取本次需要的关联文件；规划已传递完整快照内容与SHA时可直接复用。未建立的文件会返回absent；缺失资料仍需补齐或明确范围，不因取得快照而变为完整分析。

```text
python3 <study-planner>/scripts/course_records.py read-set --root <课程目录> --paths exam/items.json exam/profile.md exam/summary.json exam/brief.md
python3 <study-planner>/scripts/course_records.py bundle --root <课程目录> --role analyst --body-file <关联分析更新.json>
```

文件名按已有实际记录选取，不批量迁移旧路径。read-set要求已有课程根目录，读取期间持有与写入相同的锁，返回每个文件的内容和SHA；协作写入不能插入其中。遇到锁超时保留当前课堂接续点、稍后重试；遇到未完成批次先恢复。普通read只读取一个文件，不能用先后几个read冒充同一快照。锁不会核验题意或阻止绕开助手的编辑，采用前仍检查关联结果的范围与内容。

临时内容在side-notes；主课堂笔记用role main和kind lesson/practice。根目录及角色每次与当前课程核对。工具不可用时可顺序保存独立笔记，但共享计划的覆盖必须保留写前回读和备份；两个活跃对话无法保证写入安全时先保留独立条目，不称已同步。

写后回读。保留用户手改内容；更正说明依据，外部原资料只读，已授权管理的inbox按文件工作流校验归档，原始字节不改写。成功保存才报告已保存，失败时提供可复制的接续摘要。讲过、看过答案、提示后成功、独立成功与隔时保持分别记录；不保存内部思维过程或没有发生的错误。

同一次课堂/反馈同时改变笔记、计划与检查点时，main优先用 `bundle` 提交关联更新，避免单文件写入中断后留下旧进度。先逐项read，准备UTF-8 JSON：`{"updates":[{"path":"practice/<ID>.md","expected":"absent","content":"实际练习正文"},{"path":"current.md","expected":"<原SHA>","content":"对应的检查点正文"}]}`，需要改计划/共同事实时加入同一批。每项正文是完整更新后的文件，实际ID稳定且先与已有练习核对。全部角色、路径、JSON和旧SHA通过才更新公开记录，`current.md`最后写；未改内容保留原mtime。

```text
python3 <study-planner>/scripts/course_records.py bundle --root <课程目录> --role main --body-file <关联更新.json>
python3 <study-planner>/scripts/course_records.py recover --root <课程目录> --role main
```

批量提交是可恢复的顺序写入，并非所有文件同时原子替换。隐藏 `.course-records.pending.json` 保留中断恢复信息；存在时脚本拒绝read、read-set和普通写入。main可恢复两种批次，analyst只可用 `recover --role analyst` 恢复自己的分析批次，不能恢复或改写main的批次；aside/questions均不能恢复。恢复后回读相关记录，从实际位置接续，不能重发已保存的练习或补造学生回答。默认恢复完成该批更新；若检测到手改则保留手改、停止覆盖并报出冲突。需要取消未完成批次时有资格的角色可用 `recover --decision abort`：只回退仍匹配该批旧/新版本的文件，保留其他手改并报告路径，取消内容留 `.history/`；随后回读合并、重新核对断点再提交。新助手也能恢复旧版v1主线journal；中断中的批次应先恢复/取消，再回退Skill版本，旧助手不能恢复新增的v2journal。不能直接删journal绕过检查。

写入及read-set支持macOS/Linux的POSIX锁；Windows共享写入/快照尚不支持，读取普通旧记录不要求锁库。工具不可用时仍保留独立笔记/可复制摘要，不能宣称已经安全同步。课程文件旧格式沿用，不需要批量迁移。

协作锁、批次journal和旧版本备份保存在课程根目录的隐藏`.course-records.lock`、`.course-records.pending.json`与`.history/`中，属于恢复元数据，不是另一份课堂笔记。不擅自改Obsidian设置或删备份；用户要求调整备份存放时再选择位置。它们保护通过脚本的写入，外部编辑器不会自动遵守锁，手改仍需写前回读；不声称断电持久性、跨设备同步或任意外部编辑期间的多文件快照一致性。
