# 离线网页与按需PDF

内部准备UTF-8 JSON，不作为学生输入要求。新生成使用schema_version为3；旧v1/v2继续按原结构渲染，不批量迁移。必需字段为course、unit、kind（lesson/chapter/course）、scope、sources、items、coverage；可选intro_html串联本章问题与主题，lesson_links索引已有课笔记。章是主要阅读单元，lesson按需要使用，course只在规划确认整门课程完成后生成。

sources数组含module、path、sha256，引用实际存在的反馈快照。items每项是一节连贯正文，含id、title、source（原页/小节或题号定位）、source_refs（sources里课程相对路径）、body_html、summary_html。v3不再要求把每节分类为concept/term/derivation/exam；章节按知识联系展开，可在同一节结合概念、推导和例子。

## 正文与辅助视图

body_html直接组成默认可连续阅读的完整正文，不能把核心定义、理由或证明藏在details里。summary_html用于单独的精简视图，应保留关键路线和条件，不以摘要替代正文。以下字段按需使用：

- supplement_html、supplement_title：可折叠的补充内容和标题；不放正文不可缺的推理。
- recall：回忆问题字符串数组；hints：title/html对象数组，按起点线索、关键选择递进；answer_html：按需揭示的参考答案。hints和answer_html需有recall；未配回忆任务的正文节无需凑题。supplement_title需有supplement_html。
- related：同页其他item.id数组；aliases：便于中英文检索的别名数组。稳定锚点从item.id生成，重排不改变定位；同页先修解释必需时纳入正文，而非仅指向外部文件。
- exam_basis（requirement/past-paper/reference）与exam_reference成对出现；前两类必须采用exam-analysis反馈，reference用于清楚标注的自拟参考表达。必要英文定义与state / define / explain放在概念附近，避免重复独立单元。

每个输出主题都有稳定ID。course.md里的学习者事实、practice里的提示与结果不复制成笔记掌握状态。v1/v2旧数据的detail_html、definition和key_steps等字段仍沿用旧格式，不混入v3。

## 可选术语与关键公式

v3可选根字段terms、equations；旧v3数据不需补字段，v1/v2仍用原结构。内部JSON由模块从正文和原反馈提取，不要求学生维护索引。先写清正文，再选有查阅价值的术语/符号与反复引用的关键关系，不逐行编号。

terms每项必需id、term_zh、term_en、meaning_html、section_id、source_refs；section_id为解释所在的item.id，source_refs引用实际采用的反馈。可选symbol_html、units_html、conditions_html、aliases。meaning_html是与正文一致的短解释，首次正式定义仍在正文；符号的单位/条件按本模型填写，不能机械补齐或跨上下文合并。

equations每项必需id、title、section_id、source_refs、math_html，可选conditions_html；math_html恰含一个display="block"的MathML公式。把`<note-equation ref="公式ID"/>`放在该section_id的body_html中，恰放一次，作为公式的正文位置；编号由渲染器生成，不在正文手写易失效的编号。需要多个相邻关系时可用一个合法MathML结构表达，但不把整段证明塞成一个编号。

`<note-ref kind="equation" ref="公式ID"/>`或`<note-ref kind="term" ref="术语ID"/>`生成可定位的同页引用；ID必须存在且稳定。标记仅是内部片段语法，成品替换为正常HTML/MathML，不加载外部脚本。引用处写清选用理由；速查表和编号帮助回到解释，不替代核心定义、推导和条件。最终核验所有目标、来源、条件与实际桌面跳转。

## 反馈覆盖映射

生成前从原反馈列重要主题，随后每项coverage包含id、topic、source_refs、status、item_ids，可选source_location和reason。status为included、merged、omitted或unresolved：前两者必须指向实际item.id并共享反馈来源；merged、omitted、unresolved必须说明reason；后两者的item_ids为空。每个输出主题必须有输入主题映射。

覆盖表描述内容与来源，不含mastery或日程字段。没有采用的背景元数据不强制列作知识点。重要遗漏/待核对项在网页“本次未展开的内容”中说明；完整映射保留在网页元数据和内部数据中，供规划接收。结构合法不证明原反馈完整或推导正确，必须逐项回读原反馈核验。

## HTML与自足资源

片段采用良构HTML、figure/figcaption及原生MathML：闭合标签、<br/>、&amp;。公式例如`<math><mfrac><mn>1</mn><mi>λ</mi></mfrac></math>`。分数、积分上下限、上下标和指数采用对应的MathML结构（如mfrac、msubsup、msub、msup）；mtext用于文字标签，不把整行公式或文本速记包进mtext冒充已排版公式。不可把数学LaTeX放code/pre绕过排版；复杂公式逐式比对与实际查看。脚本拒绝脚本片段、外部加载及常见裸TeX。正文清楚解释公式和图像，不能只交付符号序列。

已核验图像可在内部JSON的img src中保存为PNG/JPEG/WebP的base64 data URL，使JSON移到另一目录后仍可独立重建；正式长期保存优先采用这种自足形式，不能依赖会清理的临时图片路径。每图解码后不超过20 MB，base64须合法且规范，声明MIME须与图片字节签名一致；渲染与发布核验使用同一私有安全助手，拒绝SVG、其他data类型及外部图像URL。旧的JSON相对图路径仍支持：渲染时限制在输入目录内，核对格式/大小并内嵌；这种旧数据仍依赖原图文件，移动时须一并保留并再次渲染核验。格式/签名校验不替代教学图像的内容与显示核验。样式与脚本随Skill安装，生成时完整嵌入HTML；成品不用携带这些资产文件或联网。检索当前整份笔记的中英文正文、名称与别名，不加载外部索引；检索切回完整视图定位正文；回忆任务本身不提前显示答案片段。禁用脚本仍应直接读完整核心正文。

可选lesson_links为title/path数组，path相对notes/，例如lessons/L01.html；用于章节索引。每份HTML独立包含正文，索引链接不是阅读依赖。

课程外预览：

```text
python3 <study-notes>/scripts/render_notes.py --input <内部草稿.json> --output <项目测试目录>/preview.html
```

正式保存时，同一稳定章ID对应JSON与HTML。先在课程外预览并核验内部草稿，再取得实际采用反馈及两份目标的旧SHA。将自足JSON用notes角色带旧SHA保存、回读核对，然后从已保存JSON发布HTML：

```text
python3 <study-planner>/scripts/course_records.py read-set --root <课程根目录> --paths lessons/<课ID>.md notes/chapters/<章ID>.json notes/chapters/<章ID>.html
python3 <study-planner>/scripts/course_records.py write --root <课程根目录> --role notes --path notes/chapters/<章ID>.json --expected <JSON旧SHA或absent> --body-file <已核验内部草稿.json>
python3 <study-planner>/scripts/course_records.py read --root <课程根目录> --path notes/chapters/<章ID>.json
python3 <study-notes>/scripts/render_notes.py --input <课程根目录>/notes/chapters/<章ID>.json --root <课程根目录> --path notes/chapters/<章ID>.html --expected <HTML旧SHA或absent>
```

sources只列实际存在且采用的反馈；read-set按实际来源扩充，不局限示例中的一课。正式JSON内嵌需要的图片，不能只在临时目录留下草稿或图像。HTML保存持共享锁，同时验证反馈/目标SHA、覆盖映射，备份、原子替换并回读；JSON也独立接受旧目标SHA保护。手改/来源冲突先合并，不改成absent强写。

JSON与HTML是分别保存，不是成对原子提交。JSON已存但HTML发布失败时保留旧HTML，由规划在既有检查点记录具体待重建范围；重新读取变化来源/目标后合并重建，不回滚课堂事实，也不把尚未成功的HTML称为已更新。两份均成功回读后交付路径与版本。notes不能bundle或recover；原main/analyst未完成批次由其维护者处理。

## 实际验收与PDF

电脑为主要排版和验收目标：断网打开单文件HTML，检查连续正文、合理行宽、目录、公式图像、三个视图、补充折叠、回忆提示/答案、同页链接、检索空结果、缩放和键盘操作。长公式局部滚动，不能挤坏桌面正文。手机为可选辅助，不要求每次做手机适配或将其设为交付门槛，也不为迁就手机删减内容、增加折叠。源码/结构检查不替代显示验收。

用户需要PDF时，用可用浏览器导出或打印保存到同一课程notes/exports/，保留课/章/课程ID和来源HTML版本。打印前恢复完整正文与全部主题、退出回忆遮答、展开补充；不能让搜索筛选省略其他内容。打印后恢复原视图、筛选和展开状态。原反馈未纳入/待核对说明仍保留。

JSON/HTML共享助手不写二进制PDF。PDF为独立阅读快照，更新网页不自动覆盖已批注文件；新导出保留旧批注。无导出工具时说明限制，不将HTML改后缀冒充PDF。实际查看分页、完整正文、中英文、公式、图表和适合iPad批注的阅读空间。未测试iPad硬件时不称硬件已验收。
