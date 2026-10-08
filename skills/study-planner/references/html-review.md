# 已做题HTML题解

在单元练习结束汇编时读取。源数据来自同一份已做题记录和已核对解析；学生尚未尝试的未来练习不加入这份题解集。

准备UTF-8 JSON：`course`、`unit`和`items`。每题包含`id`、`title`、`source`、`question_html`、`solution_html`、`attempt`和`personal_review`。`attempt`取`independent_correct`、`independent_incorrect`、`hinted`、`partial`、`shown_solution`之一；仅根据真实作答记录选择，不能为演示伪造学生表现。

HTML片段使用普通段落、列表、表格、代码和原生MathML。公式写成`<math><mfrac>...</mfrac></math>`等正常排版，不把LaTeX源码裸露给读者；生成复杂MathML后对照原解析逐式核对。片段采用良构写法：闭合标签、`<br/>`、`&amp;`，特殊符号可直接使用Unicode。片段必须有完整题干和完整解答，不能只剩最终答案。必要图像用相对于JSON文件的PNG/JPEG/WebP路径，脚本会嵌入文件。

```text
python3 <study-planner>/scripts/course_records.py read --root <课程目录> --path reviews/<单元>.html
python3 <study-planner>/scripts/render_review.py --input <已做题.json> --root <课程目录> --path reviews/<单元>.html --expected <上一步sha256或absent>
```

脚本只负责结构、嵌入资源和静态排版，不验证知识真假、来源真实性或学生掌握。它拒绝未尝试状态、重复题ID、缺失解析和外部资源；输入中仍可保存文字来源链接。共享输入JSON通过记录脚本保存；HTML输出使用上面的版本保护模式，锁/备份/写后回读适用。课程外临时预览可用--output，不把它当作共享输出保存完成。生成后实际用浏览器查看公式、表格/图示与窄屏，核对题目完整性和个人复盘。若数学排版有问题，修复输出，不把.html后缀当作已排版证据。

正常讲课保持对话直接呈现；这里的HTML是课后题解文档。实现依据：MDN Authoring MathML；离线HTML不依赖CDN或后台服务。

用户明确要求先看解析时可整理已实际展示解析的题，标shown_solution并注明未独立尝试；普通练习不提前生成未来题目答案。无浏览器时按[读取能力规则](../../course-study/references/source-checks.md)保留待显示检查状态，不能凭MathML标签合法宣称视觉验收。
