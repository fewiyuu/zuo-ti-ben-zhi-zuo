---
name: zuo-ti-ben-zhi-zuo
description: One-stop creation of Chinese exercise workbooks from textbook PDFs or OCR/MinerU LaTeX. Use when the user provides a PDF, `.tex`, Markdown OCR output, or an OCR directory and wants 做题本 PDFs, 考研/试卷精选版, OCR cleanup, full self-check, or promotional preview images. The workflow runs MinerU when needed, audits OCR before workbook generation, repairs obvious OCR/structure issues from source PDF/text, preserves numbering, outputs compact plus one-problem-per-page A4 PDFs with Chinese filenames, and exports high-resolution promo PNGs with the correct source-textbook or workbook cover as requested.
---

# 做题本制作

目标：用户只给 PDF 或 OCR 文件时，一条龙完成 OCR、审查、修补、生成和抽查。不要把校对交给用户。

## Default Workflow

1. 输入是 PDF 时，先调用 MinerU。

优先输出 `latex,md`：TeX 用于排版生成，MD 用于审查 OCR 是否漏题、错位、乱码。CLI 多格式不稳定时逐格式调用：

```powershell
mineru-open-api extract '<book.pdf>' -o '<out>\mineru_ocr' -f latex --model pipeline --ocr --formula --table --language ch --timeout 1800
mineru-open-api extract '<book.pdf>' -o '<out>\mineru_ocr' -f md --model pipeline --ocr --formula --table --language ch --timeout 1800
```

也可以直接用脚本自动做：

```powershell
uv run python scripts/build_exercise_workbook.py '<book.pdf>' --output-dir '<out>'
```

2. 先明确成品口径。

- 如果用户说“考研精选”“适合考试/试卷”“能算能证明”“不要代码题”，不要默认全书全收。只保留目标章节内适合纸笔作答的题：推导、证明、参数识别、协方差/相关函数、预测公式、简单手算估计。
- 默认删掉或不纳入：数据文件题、R/软件操作题、模拟题、画图题、真实数据拟合题、残差诊断题、开放式解释图形题、纯实践模型识别题。若题目含少量“计算并画出”，但核心仍是手算推导，可删掉画图要求或改为“计算/说明特征”，并记录这是按试卷口径处理。
- 若用户限定章节（如“只到第十章”），生成目录、题数、宣传图都必须按限定后的版本走；不要再回到全书版返工。
- 做精选版时，推荐单独生成一个筛选脚本或筛选源目录（如 `filtered_ocr`），把 `KEEP` 题号和 `OVERRIDES` 手工修补写进可重建的源文件；不要直接改生成后的 body。

3. 做题本前先审查 OCR。

- 读脚本生成的 `exercise_workbook_review.md`。
- 生成正式做题本前，先查清题目总数。默认口径不是“脚本先识别出多少就算多少”，而是逐章确认该章最后一题的题号，并把各章最后一题题号相加作为总题数基准。
- 若目录、章节标题或正文能看出每章最后一题编号，优先用“每章最后一题题号求和”来核总数；只有当源 PDF 本身章节结构就不完整时，才退回到别的统计方法。
- 对照 MD、TeX、必要时 `pdftotext -layout` 和源 PDF。
- 自动修明显问题，再继续；不要要求用户人工校对。报告中有 warning 时，由代理判断：短题如“证明定理”可放行，公式缺块/题号异常必须回源修。
- 若新 OCR 漏题但旧 OCR 结构完整，优先用旧结构作骨架，用新 OCR/MD/PDF 只补残缺题。
- 不要为了让脚本通过而下调 `--expected-count`。若用户给出章节计数或指出总数错误，先以章节计数求和为准，回源补漏题或修题号；只有源 PDF 明确少题时才调整期望值。
- 若脚本解析出的总题数与“各章最后一题题号之和”不一致，默认视为漏题或误切题，必须先修到一致，再允许进入正式 PDF 生成。
- 若用户指出一处错误，不要只修这一处。先判断它属于哪类 OCR 结构问题，再对 TeX、MD、生成 body 做同类全量扫描、批量修复、重建验证，并在最终回复明确“已按同类问题全量处理”。
- 若用户纠正总题数或某章题数，优先重新核章节题数。常见原因包括星号题号、题号独占一行、题号后公式换行、题号被识别进上一题。必要时给 `--question-pattern` 增加允许 `*` 和空题干行的规则，不能用错误的期望值绕过。
- 对第一轮扫描结果要分两层判断：OCR 源稿中的教材正文、例题或未进入习题的表格可以有噪声；生成后的 `exercise_workbook_*_body.tex` 才是成品正文。必须分别扫，不能把 OCR 源噪声误报为成品问题，也不能只因脚本审查通过就跳过成品正文扫描。
- 若源 PDF 是 LaTeX/电子版正文（而不是扫描图片 PDF），通常无法“直接抽出每页原图”做校对；这类文件的页内容主要是文字、公式和矢量对象。对它们应以 OCR 源稿 `md/tex` 和生成后的 body 为主做文本级审查，整页渲染图只用于成品视觉抽查，不作为唯一真值来源。
- 自查不要只看脚本报告。报告通过后仍要扫成品 `exercise_workbook_*_body.tex`，重点查 OCR 残渣、错下标、空格化公式、混入的实操题，以及最终 PDF 渲染问题。

常见必须修的坑：

- 题目总数或章节题数异常。
- 各章最后一题题号之和与脚本识别总数不一致。
- 单题内容为空或极短。
- 正文混入 `\begin{document}`、`\end{document}`、`\maketitle`。
- 残留 `\begin{enumerate}`、`\setcounter`、`\tightlist` 把题号包坏。
- 题号粘连或误识别，例如 `8.64` 实为第 8 题且题干以“64 只...”开头。
- 明显 OCR 错字：`末知`、`做马分布`、`几匀分布`、`a1, θ`、裸 `L(a1, θ)=`。
- 公式或损失函数只剩小问标号 `(a).`、`(b).`。
- 坏表格或分布列：Markdown 残留 `<table>`、表格行被压成 `0 n` / `1 1 n n`、根号被识别成 `√nk`、概率行缺 `1/2`。生成 body 里的 `longtable` 不自动视为错误；若表格来自题目数据且能编译渲染，可保留，但要抽查宽表是否截断。
- 表格版式被过度拆分：宽表不应为了避宽而无必要拆成多张上下排列的 `longtable`，尤其在留白版一题一页时会把同一题切到下一页。短表和可压缩长表优先保持同题同页；只有确实无法读清或无法放入页面时才拆。
- 明显乱码和公式名空格化：如 `LK(b)`、`p _ { : }`、`入2`、`Biak-chole`、`Eε`、`Dε`、`sharp`、`\dag`、`\ddag`、`\oplus`、`\succeq`、`\alpha \bullet \beta`、`\alpha \cdot \beta`、`\forall x /`、`\mathbf{\dot{q}}`、`P _ { \theta } |`、`operatorname* { m a x }`、`operatorname* { l i m }`、空的 `\stackrel { P } {  }` / `\overset { P } {  }`。
- 小问结构异常：如 `(3)` 被识别成 `P1`、漏掉后续 `(4)`、证明题或问答题只剩编号没有题干。遇到这种情况必须回源 PDF 页面对照，而不是猜。
- 参数与随机变量误识别：如 `总体s` / `总体n` 应为 `总体 \xi` / `总体 \eta`，`q×n` 或列向量被识别成带点字母，`\alpha,\beta` 被识别成点乘或项目符号。

发现上述任一类后，至少跑一次类似扫描，并根据本书实际内容增删模式：

```powershell
rg -n "<table>|√|0 n|1 1 n n|LK|p _ \{ : \}|入2|Biak|chole|Eε|Dε|sharp|\\dag|\\ddag|\\oplus|\\succeq|\\alpha \\bullet \\beta|\\alpha \\cdot \\beta|P1|总体s|总体n|forall x /|operatorname\* \{ [a-z] [a-z]|stackrel \{ P \} \{  \}|overset \{ P \} \{  \}" '<out>\mineru_ocr'
rg -n -g 'exercise_workbook_*_body.tex' "sharp|\\dag|\\ddag|\\oplus|\\succeq|P _ \{ \\theta \} \||\\forall x /|\\mathbf \{ \\dot \{ q \} \}|\\alpha \\bullet \\beta|\\alpha \\cdot \\beta|P1|总体s|总体n|末知|做马分布|几匀分布|8\.64|入2|Biak|chole|Eε|Dε|p _ \{ : \}|LK|begin\{enumerate\}|end\{document\}|maketitle|stackrel \{ P \} \{  \}|overset \{ P \} \{  \}|operatorname\* \{ [a-z] [a-z]" '<out>'
```

修补原则：

- 同步修 OCR 源 TeX 和 MD；不要只改生成后的 body 或 PDF。
- 分布列优先改成稳定的 `array`，例如 `\begin{array}{c|cc} ... \end{array}`，并对照 `pdftotext -layout` 或源 PDF 确认数值。
- 题内数据表优先保持完整：先尝试 `tabular`、`array`、`\footnotesize`/`\scriptsize`、适度缩小 `\tabcolsep` 和 `\arraystretch`、横向并排 `minipage`，再考虑拆表。拆表时优先同页并排，不要默认上下分成多张会跨页的 `longtable`。
- 对 10--40 行的双块数据表，可把左、右指标分别做成两个 `minipage` 内的 `tabular` 并排；对 10 多行以内的宽表，通常恢复为单张小字号 `tabular` 比拆成两张更好。
- 英文专名、参数下标、收敛箭头、`max/min/lim` 等可高置信修复的 OCR 噪声一并清掉；不确定的复杂公式不要瞎补。
- 对复杂缺块，先用 `pdftotext -layout` 定位，再渲染源 PDF 相邻页截图核对。特别是题尾跨页、小问跨页、分段函数第二行条件、似然函数花括号和概率分布列。
- 重建后再次扫描生成 body。若只剩正常范围写法（如 `5000\textasciitilde10000`）或正常题目数据表，记录为已判定正常；其他高危命中继续回源修。
- 若需要人工快速通读整本成品，优先先看 `[A4紧凑]` 版：把全书按页转成 PNG，再做 4--6 页一组的 contact sheet 总览，先定位哪几页最可疑、哪几页最能体现质量，再回看单页。不要一开始就逐张看留白版。
- 对“肉眼一看就不对”的 OCR 错字与残渣，要优先修：例如孤立的 `十`、`I`、`T`、`XX`、`ik>`、`11K`、`公`、`概率. ?`、`P(aX^T=b); 1`、`存在R上Borel`、题号后尾巴粘连等。这类问题通常不影响题数统计，但会明显损伤成品质感。
- 对时间序列类教材，额外高频查：`\phi_z` 应多半为 `\phi_2`，`0 , 7`/`0 . 5` 这类小数 OCR，`\{Y)`/`\{Y,`，`\operatorname { V a r }`，`\operatorname { C o v }`，`\smash`，`\boldsymbol`，`\scriptstyle`，以及“画出/数据文件/模拟/残差/诊断/试探性设定”等不适合考研精选的词。

对无法安全规则修复的复杂缺块，使用 MD、TeX、`pdftotext -layout`、源 PDF 页面截图交叉还原；只在最终说明仍可能有 OCR 残余风险，不中途打断用户。

4. 生成做题本。

```powershell
uv run python scripts/build_exercise_workbook.py '<ocr-or-pdf>' `
  --book-title '书名' `
  --expected-count 263 `
  --expected-chapter-counts '12,55,51,36,57,22,30' `
  --strict-review
```

默认输出：

- `[A4紧凑] 书名 做题本.pdf`
- `[A4留白] 书名 做题本.pdf`
- `exercise_workbook_review.md`
- `promo_images\宣传图_01_封面.png`
- `promo_images\宣传图_02_一页一题_第N页.png` 等宣传图
- 中间 TeX/body 文件，便于继续自动修补。

注意：书名过长时，`--book-title` 可用短显示名，避免封面标题与副标题重叠；文件名和正文内容不必因此回退。

5. 输出宣传图。

默认从 `[A4留白] 书名 做题本.pdf` 渲染 5 张 A4 300 DPI PNG，放在 `promo_images`：

- 宣传图通常要同时包含“教材封面”和“做题本封面”。若用户明确只要其中一种，再按用户指定；否则默认输出双封面：`宣传图_01_教材封面.png`、`宣传图_02_做题本封面.png`。
- 教材封面必须从源教材 PDF 第 1 页渲染；做题本封面从留白版或紧凑版第 1 页渲染。用户说“带上教材封面/原书封面/不是做题本封面”时，不代表可以省略做题本封面，除非用户明确说只要教材封面。
- 后 4 张从一页一题正文页中分散选取，优先挑“长题干 + 多小问 + 公式/表格/推导较密”的页面；避免只截一句话就结束的短题页，因为这类图看不出做题本质量。不要输出总览拼图。
- 文件名使用中文稳定命名：`宣传图_01_教材封面.png`、`宣传图_02_做题本封面.png`、`宣传图_03_一页一题_第81页.png`。
- 若要手动指定页码，用 `--promo-pages '1,81,121,151,261'`；若只想生成 PDF，用 `--skip-promo`。
- 若脚本默认宣传图不支持“双封面”，可手动用 `pdftoppm -png -singlefile -f 1 -l 1 -r 300 原教材.pdf promo_images\宣传图_01_教材封面`，再从做题本第 1 页渲染 `宣传图_02_做题本封面`，再从留白版渲染 4 张正文样张。
- 生成后检查尺寸应为 A4 300 DPI（通常 `2481 x 3508`；教材原封面可能不是 A4，保持源封面比例即可），并抽看封面和至少两张正文图，确保不空白、不截断、不乱码，且样张确实能体现公式密度或题目复杂度。

6. 最终抽查。

- 确认脚本报告中的题数和章节题数。
- 搜索残留高危标记：`\end{document}`、`begin{enumerate}`、`a1, θ`、`8.64`、`末知`、`做马分布`、`<table>`、`p _ { : }`、`sharp`、`\dag`、`\ddag`、`\oplus`、`\succeq`、`\alpha \bullet \beta`、`\alpha \cdot \beta`、`P1`、`总体s`、`总体n`、空的概率收敛箭头。
- 搜索命中要分类：OCR 源稿命中、生成 body 命中、最终 PDF 可见问题。最终 PDF 只由生成 body 决定；OCR 源稿里未进入习题的教材正文噪声不必修到完美，但进入习题的问题必须修。
- 用 XeLaTeX 编译日志确认无 `!` 错误；脚本默认 `--latex-engine auto`，先 XeLaTeX，失败再 LuaLaTeX。
- 用 `pdftotext` 定位修补过的题页，再用 `pdftoppm` 渲染抽查；表格、分式、根号、上下标不能缺块或挤坏。
- 若用户要求“整本看完”，就真的把 `[A4紧凑]` 版 20 多页全部过一遍。建议先做 contact sheet 总览，再逐页放大可疑页，而不是只抽几页象征性检查。
- 留白版是一题一页时，页数应接近“封面 + 目录 + 题目数”。若明显多出页数，优先排查题内表格、公式或图片是否被迫跨页；不要接受“同一题表格拆到第二页”作为默认结果。
- 注意区分“PDF 物理页数”和页脚中的正文编号总页数。若留白版有封面并且目录单独编号，常见情况是 PDF 总页数 = `封面 1 + 目录 1 + 题目数`，而页脚中的“共 N 页”只统计正文编号页，不一定含封面。
- 对用户指出的表格问题，至少渲染该表所在页和相邻页检查；确认表头、末行、左右/上下表块都在同一题页内，且没有被页脚、页边或下一题截断。
- 若修过一类问题，抽查至少 2-3 个代表页，而不是只看用户指出的那一页。
- 确认 `promo_images` 中没有 `宣传图_总览预览.png` 之类拼图，只保留教材封面、做题本封面和一页一题样张；确认 `宣传图_01_教材封面.png` 真来自源教材 PDF 第 1 页，`宣传图_02_做题本封面.png` 真来自做题本第 1 页。
- 封面也要渲染抽看。长书名可能在封面重叠，即使正文正常也要修短显示书名或调整封面布局后重建。
- 清理临时页码定位文本和 `page_checks` 等验证产物，只保留正式 PDF、OCR 源、审查报告和宣传图。

## Script

主脚本：

```powershell
uv run python scripts/build_exercise_workbook.py <PDF或tex目录> [options]
```

常用选项：

- `--ocr`：即使已有 TeX，也重新从 PDF 跑 MinerU。
- `--ocr-formats latex,md`：默认值，逐格式提取；正式流程建议保持。
- `--expected-count N`：期望总题数，不一致写报告。
- `--expected-chapter-counts '12,55,...'`：期望各章题数。
- `--strict-review`：审查有 error 时停止编译；现在脚本默认开启。
- `--no-strict-review`：仅用于调试中间结果时关闭严格审查。
- `--latex-engine auto|xelatex|lualatex`：默认 auto。
- `--skip-compile`：只生成 TeX/body 和审查报告。
- `--skip-promo`：不生成宣传图。
- `--promo-count N`：宣传图张数，默认 5。
- `--promo-dpi N`：宣传图 DPI，默认 300。
- `--promo-pages '1,81,121,151,261'`：手动指定宣传图 PDF 页码；默认自动选“封面 + 分散正文页”。
- `--promo-pages '1,174,175,226,272'`：像这种做题本更适合作为“内容密度优先”的手工样张页示例。
- `--question-pattern`：补充题号规则。

## Notes

- 以后默认输出中文文件名。
- 以后默认同时输出中文版 PDF 和宣传图：封面 + 一页一题样张，不要输出总览图。
- 优先用 XeLaTeX；只有字体/引擎问题时才用 LuaLaTeX 兜底。
- MD 更适合审查，TeX 更适合生成 PDF；两者都要保留。
- 若 OCR 结果互相矛盾，不全量替换。保留题号结构最完整的一版作骨架，再从更清楚的 OCR/MD/PDF 补局部。
- 正式流程推荐默认组合：全量 OCR、`pipeline`、`latex,md`、`formula/table` 开启、填写 `expected-count` 与 `expected-chapter-counts`、保持严格审查开启。
