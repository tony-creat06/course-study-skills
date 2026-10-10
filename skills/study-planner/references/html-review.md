# 已做题HTML题解

在单元练习结束汇编时读取。源数据来自同一份已做题记录和已核对解析；学生尚未尝试的未来练习不加入这份题解集。

准备UTF-8 JSON：`course`、`unit`和`items`。每题包含`id`、`title`、`source`、`question_html`、`solution_html`、`evidence`和`personal_review`。只从同一份真实练习记录派生显示证据，不能为演示伪造学生表现。

`evidence`把帮助条件和结果分开：

- `assistance`：`none`（本次作答前/中无关键提示）、`hint`、`solution`、`mixed`、`unknown`。完成之后才展示解析不反向改变原独立作答条件。
- `outcome`：`correct`、`incorrect`、`partial`、`not_attempted`、`mixed`。未尝试的未来题不加入；用户已明确索要并看过完整解析时可用solution与not_attempted，注明未独立尝试。
- `reproduction`、`delayed`：可选true/false/null，分别说明已见同题解法后的实际再现、隔时回访；未知留null/省略。隔时标签只描述观察条件，不表示长期掌握。

例如 `{ "assistance": "hint", "outcome": "partial" }` 表示提示后仍只部分完成。`mixed`时在personal_review保留各小问帮助与结果。不能用一个整体正确标签覆盖不同小问的实际情况；同题多次尝试的日期/提示/变化继续保留在原练习记录和复盘中。

旧JSON的`attempt`仍可读取，不批量改旧课程：独立正确/需订正、partial、shown_solution沿用；hinted只显示“本题使用过提示（结果见复盘）”，不再自动推断完成。新记录使用evidence；同一item不能同时写两个版本的字段。

HTML片段使用普通段落、列表、表格、代码和原生MathML。公式写成`<math><mfrac>...</mfrac></math>`等正常排版，不把LaTeX源码裸露给读者；生成复杂MathML后对照原解析逐式核对。片段采用良构写法：闭合标签、`<br/>`、`&amp;`，特殊符号可直接使用Unicode。片段必须有完整题干和完整解答，不能只剩最终答案。必要图像用相对于JSON文件的PNG/JPEG/WebP路径，脚本会嵌入文件。

```text
python3 <study-planner>/scripts/course_records.py read --root <课程目录> --path reviews/<单元>.html
python3 <study-planner>/scripts/render_review.py --input <已做题.json> --root <课程目录> --path reviews/<单元>.html --expected <上一步sha256或absent>
```

脚本只负责结构、嵌入资源和静态排版，不验证知识真假、来源真实性或学生掌握。它拒绝尚未尝试且未展示解析的未来题、重复题ID、缺失解析和外部资源；输入中仍可保存文字来源链接。共享输入JSON通过记录脚本保存；HTML输出使用上面的版本保护模式，锁/备份/写后回读适用。课程外临时预览可用--output，不把它当作共享输出保存完成。生成后实际用浏览器查看公式、表格/图示与窄屏，核对题目完整性和个人复盘。若数学排版有问题，修复输出，不把.html后缀当作已排版证据。

正常讲课保持对话直接呈现；这里的HTML是课后题解文档。实现依据：MDN Authoring MathML；离线HTML不依赖CDN或后台服务。

用户明确要求先看解析时可整理已实际展示解析的题，按上述帮助/结果注明未独立尝试；普通练习不提前生成未来题目答案。无浏览器时按[读取能力规则](../../course-study/references/source-checks.md)保留待显示检查状态，不能凭MathML标签合法宣称视觉验收。
