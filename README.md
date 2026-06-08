# 做题本制作 Skill

一个 Codex skill：从教材 PDF、MinerU/OCR 输出或 LaTeX 中抽取习题，生成可打印的 A4 做题本。

## 安装

推荐下载 Release 里的 `zuo-ti-ben-zhi-zuo.zip`，解压后会得到同名文件夹：

```text
zuo-ti-ben-zhi-zuo/
  SKILL.md
  agents/
  scripts/
```

把这个 `zuo-ti-ben-zhi-zuo` 文件夹放到：

```powershell
$env:USERPROFILE\.codex\skills\
```

也可以直接 clone 到 skill 目录：

```powershell
git clone https://github.com/fewiyuu/zuo-ti-ben-zhi-zuo.git "$env:USERPROFILE\.codex\skills\zuo-ti-ben-zhi-zuo"
```

## 使用

在 Codex 里说：

```text
Use $zuo-ti-ben-zhi-zuo to 把这本 PDF 做成做题本
```

脚本也可以单独跑：

```powershell
uv run python scripts/build_exercise_workbook.py "<PDF或OCR目录>" --output-dir "<输出目录>"
```

可选依赖：MinerU OCR、LaTeX `latexmk`、Poppler `pdftoppm`。

License: MIT
