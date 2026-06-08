from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
__version__ = "0.1.0"
DEFAULT_BRAND = "Exercise Workbook"


HEADING_LEVELS = {
    "part": 0,
    "chapter": 1,
    "section": 2,
    "subsection": 3,
    "subsubsection": 4,
    "paragraph": 5,
    "subparagraph": 6,
}

HEADING_OPEN_RE = re.compile(
    r"^\s*\\(?P<cmd>part|chapter|section|subsection|subsubsection|paragraph|subparagraph)\*?\{"
)
LABEL_RE = re.compile(r"\\label\{[^}]*\}")
INCLUDEGRAPHICS_RE = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{(?P<path>[^}]+)\}")
WHITESPACE_RE = re.compile(r"\s+")
TRAILING_PAGE_RE = re.compile(r"\s+\d+\s*$")
ENUM_COUNTER_RE = re.compile(r"\\setcounter\{(?P<name>enum\w*)\}\{(?P<value>\d+)\}")
ITEM_RE = re.compile(r"^\s*\\item(?:\[[^\]]*\])?\s*(?P<rest>.*)$")
LABEL_ENUM_RE = re.compile(r"\\def\\label(?P<name>enum\w*)")
CHAPTER_ONLY_RE = re.compile(r"^第\s*(?P<num>[0-9一二三四五六七八九十百千零〇两]+)\s*章$")
CHAPTER_FULL_RE = re.compile(
    r"^第\s*(?P<num>[0-9一二三四五六七八九十百千零〇两]+)\s*章\s*(?P<title>.+?)$"
)
LEADING_DECIMAL_RE = re.compile(r"^(?P<num>\d+(?:\.\d+)*)")
EDITION_RE = re.compile(r"第\s*([0-9一二三四五六七八九十百千零〇两]+)\s*版")

DEFAULT_EXERCISE_KEYWORDS = [
    "习题",
    "练习",
    "课后习题",
    "复习题",
    "思考题",
    "exercises",
    "exercise",
    "problems",
    "problem set",
]
DEFAULT_EXCLUDE_KEYWORDS = [
    "答案",
    "解析",
    "解答",
    "提示",
    "参考答案",
    "小结",
    "总结",
    "附录",
    "杂录",
    "solutions",
    "solution",
    "answers",
    "answer",
    "notes",
    "note",
]
DEFAULT_QUESTION_PATTERNS = [
    r"^(?P<num>[1-9]\d*)[\.．]\s*(?P<rest>(?!\d)(?!$).*)$",
    r"^(?P<num>[1-9]\d*)[\.．]\s*$",
    r"^(?P<num>\d+\.\d+)\s+(?!&)(?P<rest>.*)$",
    r"^(?P<num>\d+\.\d+)\s*$",
    r"^(?P<num>第\s*\d+\s*题)\s*(?P<rest>.*)$",
    r"^(?P<num>(?:Problem|Exercise|Ex\.)\s*\d+)\s*[:.)-]?\s*(?P<rest>.*)$",
]
BOOK_TITLE_IGNORE_PATTERNS = [
    re.compile(pattern, re.I)
    for pattern in (
        r"^目录$",
        r"^contents?$",
        r"^出版说明$",
        r"^图书在版编目",
        r"^译后序$",
        r"^前言$",
        r"^后记$",
        r"^附录",
        r"^参考文献$",
        r"^作者索引$",
        r"^名词索引$",
        r"^preface$",
        r"^acknowledg",
        r"^第\s*[0-9一二三四五六七八九十百千零〇两]+\s*版序$",
        r"^第\s*[0-9一二三四五六七八九十百千零〇两]+\s*章",
        r"^\d+(?:\.\d+)*",
    )
]
IGNORED_DIR_NAMES = {
    ".git",
    ".cache",
    ".cache-home",
    "exercise_book_output",
    "skill_test_output",
}
CN_DIGITS = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
CN_UNITS = {"十": 10, "百": 100, "千": 1000}
CN_SMALL_TEXT = {
    0: "零",
    1: "一",
    2: "二",
    3: "三",
    4: "四",
    5: "五",
    6: "六",
    7: "七",
    8: "八",
    9: "九",
    10: "十",
}
SUPPORTED_LATEX_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".pdf"}
LATEX_ENGINES = ("auto", "xelatex", "lualatex")
DEFAULT_PROMO_COUNT = 5
DEFAULT_PROMO_DPI = 300
REVIEW_PATTERNS = [
    ("error", "混入文档边界命令", re.compile(r"\\(?:begin|end)\{document\}|\\maketitle")),
    ("warning", "残留 enumerate 结构", re.compile(r"\\(?:begin|end)\{enumerate\}|\\setcounter\{enum")),
    ("warning", "疑似 OCR 替换字符", re.compile(r"�|□|■|\u001a")),
    ("warning", "疑似错误 TeX 命令残片", re.compile(r"\\nleq|\\not\s*=\s*\\not|\\overrightarrow|\\underline")),
    ("warning", "常见 OCR 错字", re.compile(r"末知|做马分布|几匀分布")),
    ("warning", "损坏的题号或公式片段", re.compile(r"8\.64|a1,\s*θ|L\s*\(a1")),
]
SAFE_TEXT_REPLACEMENTS = {
    "末知": "未知",
    "做马分布": "伽马分布",
    "几匀分布": "几何分布",
    "0−1": "0-1",
    "0－1": "0-1",
    "C − R": "C-R",
    "C−R": "C-R",
}

COMMON_PREAMBLE = r"""
\usepackage{amsmath,amssymb,amsfonts,bm}
\usepackage{mathrsfs}
\usepackage[version=4]{mhchem}
\usepackage{stmaryrd}
\usepackage{bbold}
\usepackage{graphicx}
\usepackage[export]{adjustbox}
\usepackage{array,booktabs,longtable,multirow,tabularx}
\usepackage{enumitem}
\usepackage{etoolbox}
\usepackage{footnote}
\usepackage{titlesec}
\usepackage{setspace}
\usepackage{hyperref}
\usepackage{xcolor}
\usepackage{fancyhdr}
\usepackage{tocloft}
\usepackage{tikz}
\usepackage{lastpage}

\IfFontExistsTF{Times New Roman}
  {\setmainfont{Times New Roman}}
  {\setmainfont{TeX Gyre Termes}}
\IfFontExistsTF{Arial}
  {\setsansfont{Arial}}
  {\setsansfont{TeX Gyre Heros}}
\setmonofont{Latin Modern Mono}
\IfFontExistsTF{SimSun}
  {%
    \setCJKmainfont[BoldFont=SimHei,ItalicFont=KaiTi]{SimSun}
    \setCJKsansfont{Microsoft YaHei}
    \setCJKmonofont{FangSong}
  }
  {%
    \setCJKmainfont[BoldFont=FandolSong-Bold,ItalicFont=FandolKai-Regular]{FandolSong-Regular}
    \setCJKsansfont{FandolHei-Regular}
    \setCJKmonofont{FandolFang-Regular}
  }

\hypersetup{hidelinks}
\urlstyle{same}
\setlength{\parindent}{0pt}
\setlength{\parskip}{3pt}
\setlength{\abovedisplayskip}{5pt plus 1pt minus 1pt}
\setlength{\belowdisplayskip}{5pt plus 1pt minus 1pt}
\setlength{\abovedisplayshortskip}{3pt plus 1pt}
\setlength{\belowdisplayshortskip}{3pt plus 1pt}
\setlength{\emergencystretch}{3em}
\allowdisplaybreaks
\raggedbottom
\setlist{itemsep=1pt,topsep=2pt,parsep=0pt,partopsep=0pt,leftmargin=*}
\providecommand{\tightlist}{%
  \setlength{\itemsep}{0pt}\setlength{\parskip}{0pt}}
\newcounter{none}
\makesavenoteenv{longtable}

\makeatletter
\patchcmd\longtable{\par}{\if@noskipsec\mbox{}\fi\par}{}{}
\newsavebox\pandoc@box
\newcommand*\pandocbounded[1]{%
  \sbox\pandoc@box{#1}%
  \Gscale@div\@tempa{\textheight}{\dimexpr\ht\pandoc@box+\dp\pandoc@box\relax}%
  \Gscale@div\@tempb{\linewidth}{\wd\pandoc@box}%
  \ifdim\@tempb\p@<\@tempa\p@\let\@tempa\@tempb\fi%
  \ifdim\@tempa\p@<\p@\scalebox{\@tempa}{\usebox{\pandoc@box}}%
  \else\usebox{\pandoc@box}%
  \fi%
}
\makeatother
""".strip()


@dataclass
class Heading:
    command: str
    level: int
    title: str
    line_start: int
    line_end: int


@dataclass
class ChapterContext:
    label: str | None = None
    number: int | None = None
    title: str | None = None

    @property
    def display(self) -> str:
        parts = [part for part in (self.label, self.title) if part]
        return " ".join(parts).strip()


@dataclass
class ExerciseSection:
    chapter_key: str
    chapter_display: str
    section_title: str
    lines: list[str]
    sort_bucket: int
    numeric_key: tuple[int, ...]
    source_order: int
    heading_order: int


@dataclass
class Question:
    chapter_key: str
    chapter_display: str
    number: str
    lines: list[str]


@dataclass
class ReviewFinding:
    level: str
    scope: str
    message: str
    excerpt: str = ""


def normalize_text(text: str) -> str:
    return WHITESPACE_RE.sub(" ", text).strip()


def strip_trailing_page_number(text: str) -> str:
    return TRAILING_PAGE_RE.sub("", text).strip()


def normalize_heading_title(text: str) -> str:
    return normalize_text(strip_trailing_page_number(text))


def split_csv_arg(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def format_alpha_enum(counter: int) -> str:
    if counter <= 0:
        return "(a)"
    counter -= 1
    letters: list[str] = []
    while True:
        counter, remainder = divmod(counter, 26)
        letters.append(chr(ord("a") + remainder))
        if counter == 0:
            break
        counter -= 1
    return "(" + "".join(reversed(letters)) + ")"


def tex_escape(text: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in text)


def sanitize_filename_prefix(raw: str) -> str:
    value = raw.strip() or "exercise_workbook"
    value = re.sub(r"[<>:\"/\\|?*]+", "-", value)
    value = re.sub(r"\s+", "_", value)
    value = value.strip(" ._-")
    return value or "exercise_workbook"


def sanitize_artifact_filename(raw: str) -> str:
    value = raw.strip() or "做题本"
    value = re.sub(r"[<>:\"/\\|?*]+", "-", value)
    value = re.sub(r"\s+", " ", value)
    value = value.strip(" ._-")
    return value or "做题本"


def chinese_pdf_name(book_title: str, variant: str) -> str:
    clean_title = sanitize_artifact_filename(book_title or "做题本")
    return f"[A4{variant}] {clean_title} 做题本.pdf"


def parse_cn_number(token: str) -> int | None:
    if token.isdigit():
        return int(token)
    total = 0
    current = 0
    for char in token:
        if char in CN_DIGITS:
            current = CN_DIGITS[char]
            continue
        if char in CN_UNITS:
            unit = CN_UNITS[char]
            if current == 0:
                current = 1
            total += current * unit
            current = 0
            continue
        return None
    return total + current if total + current > 0 else None


def format_cn_small_number(number: int) -> str:
    if number <= 10:
        return CN_SMALL_TEXT[number]
    if number < 20:
        return "十" + CN_SMALL_TEXT[number - 10]
    if number < 100:
        tens, units = divmod(number, 10)
        text = CN_SMALL_TEXT[tens] + "十"
        if units:
            text += CN_SMALL_TEXT[units]
        return text
    return str(number)


def contains_cjk(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def looks_like_numbered_heading(text: str) -> bool:
    if CHAPTER_ONLY_RE.match(text) or CHAPTER_FULL_RE.match(text):
        return True
    return bool(re.match(r"^\d+(?:\.\d+)*", text))


def is_probable_book_title(text: str) -> bool:
    if not text or len(text) > 48:
        return False
    if looks_like_numbered_heading(text):
        return False
    lowered = text.casefold()
    return not any(pattern.search(lowered) for pattern in BOOK_TITLE_IGNORE_PATTERNS)


def clean_stem_title(path: Path) -> str:
    stem = path.stem
    stem = re.sub(r"^MinerU_latex_", "", stem, flags=re.I)
    stem = re.sub(r"_\d{6,}$", "", stem)
    stem = stem.replace("_", " ").strip()
    return stem or "做题本"


def infer_book_title(headings: list[Heading], tex_files: list[Path]) -> str:
    candidates: list[tuple[int, int, int, int, int, str]] = []
    edition = ""

    for source_order, tex_file in enumerate(tex_files):
        file_lines = tex_file.read_text(encoding="utf-8").splitlines()
        file_headings = parse_headings(file_lines)
        first_chapter_index: int | None = None

        for index, heading in enumerate(file_headings):
            normalized = normalize_heading_title(heading.title)
            if first_chapter_index is None and (
                CHAPTER_ONLY_RE.match(normalized) or CHAPTER_FULL_RE.match(normalized)
            ):
                first_chapter_index = index
            if not edition:
                match = EDITION_RE.search(normalized)
                if match:
                    token = match.group(1)
                    parsed = parse_cn_number(token)
                    edition_token = (
                        format_cn_small_number(parsed) if parsed is not None else token
                    )
                    edition = f"第{edition_token}版"

        for index, heading in enumerate(file_headings[:80]):
            title = normalize_heading_title(heading.title)
            if not is_probable_book_title(title):
                continue
            zone_rank = 0 if first_chapter_index is not None and index < first_chapter_index else 1
            language_rank = 0 if contains_cjk(title) else 1
            candidates.append(
                (zone_rank, language_rank, len(title), source_order, index, title)
            )

    if candidates:
        base_title = sorted(candidates)[0][-1]
    elif tex_files:
        base_title = clean_stem_title(tex_files[0])
    else:
        base_title = "做题本"

    if edition and edition not in base_title:
        base_title = f"{base_title}{edition}"
    return base_title


def prepare_cover_image(cover_image: str | None, out_dir: Path) -> str | None:
    if cover_image:
        source = Path(cover_image).expanduser().resolve()
    else:
        return None

    if not source.exists():
        raise FileNotFoundError(f"封面图片不存在: {source}")

    asset_dir = out_dir / "cover_assets"
    asset_dir.mkdir(parents=True, exist_ok=True)

    suffix = source.suffix.lower()
    if suffix in SUPPORTED_LATEX_IMAGE_SUFFIXES:
        target = asset_dir / f"cover-image{suffix}"
        shutil.copy2(source, target)
        return target.relative_to(out_dir).as_posix()

    target = asset_dir / "cover-image.png"

    magick_cmd = shutil.which("magick")
    if magick_cmd:
        subprocess.run([magick_cmd, str(source), str(target)], check=True)
        return target.relative_to(out_dir).as_posix()

    try:
        from PIL import Image  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "封面图片格式需要转换，但当前环境缺少 Pillow。请用 uv run --with pillow 运行，或改用 png/jpg 图片。"
        ) from exc

    with Image.open(source) as image:
        image.convert("RGBA").save(target)
    return target.relative_to(out_dir).as_posix()


def split_book_title_for_cover(book_title: str) -> tuple[str, str | None]:
    normalized = book_title.strip()
    match = re.match(
        r"^(?P<main>.*?)(?P<edition>第[0-9一二三四五六七八九十百千零〇两]+版)$",
        normalized,
    )
    if match:
        return match.group("main").strip(), match.group("edition").strip()
    return normalized, None


def infer_cover_english_label(book_title: str) -> str:
    return "EXERCISE NOTEBOOK"


def build_cover_image_snippet(cover_image_rel: str | None) -> str:
    if not cover_image_rel:
        return ""
    return rf"""
    \fill[black,opacity=0.14]
      ([xshift=-2.55cm,yshift=-8.15cm]current page.north east) circle (2.08cm);
    \begin{{scope}}
      \clip ([xshift=-2.65cm,yshift=-8.05cm]current page.north east) circle (2.02cm);
      \node at ([xshift=-2.65cm,yshift=-8.05cm]current page.north east) {{
        \includegraphics[width=4.3cm,height=4.3cm]{{{cover_image_rel}}}
      }};
    \end{{scope}}
    \draw[white,line width=1.6pt]
      ([xshift=-2.65cm,yshift=-8.05cm]current page.north east) circle (2.02cm);
    """


def build_compact_tex(
    book_title: str,
    brand: str,
    body_name: str,
    question_count: int,
    chapter_count: int,
    include_cover: bool,
    include_toc: bool,
    cover_image_rel: str | None,
) -> str:
    header_title = tex_escape(book_title or "做题本")
    header_brand = tex_escape(brand or DEFAULT_BRAND)
    variant_label = tex_escape("紧凑版")
    cover_title_main_raw, cover_title_edition_raw = split_book_title_for_cover(book_title or "做题本")
    cover_title_main = tex_escape(cover_title_main_raw)
    cover_title_edition = tex_escape(cover_title_edition_raw) if cover_title_edition_raw else ""
    edition_block = (
        rf"{{\fontsize{{22}}{{27}}\selectfont\bfseries\color{{covermuted}} {cover_title_edition}\par}}"
        if cover_title_edition
        else ""
    )
    small_label = tex_escape(infer_cover_english_label(book_title or "做题本"))
    subtitle = tex_escape("做题本")
    tagline = tex_escape("练习整理专用 · 适合打印留存")
    cover_image = build_cover_image_snippet(cover_image_rel)
    workbook_cover_flag = r"\workbookcovertrue" if include_cover else r"\workbookcoverfalse"
    workbook_toc_flag = r"\workbooktoctrue" if include_toc else r"\workbooktocfalse"
    return rf"""
\documentclass[10pt,a4paper,fontset=none]{{ctexart}}
\usepackage[top=1.65cm,bottom=1.55cm,left=2.1cm,right=2.1cm,headheight=16pt,headsep=4pt,footskip=18pt]{{geometry}}
{COMMON_PREAMBLE}

\definecolor{{worksheetline}}{{RGB}}{{80,80,80}}
\definecolor{{worksheetink}}{{RGB}}{{18,18,18}}
\definecolor{{worksheetmuted}}{{RGB}}{{70,70,70}}
\definecolor{{coverbg}}{{RGB}}{{251,250,247}}
\definecolor{{coverbarlight}}{{RGB}}{{200,214,228}}
\definecolor{{coverbardark}}{{RGB}}{{150,169,191}}
\definecolor{{coveraccent}}{{RGB}}{{112,137,166}}
\definecolor{{covermuted}}{{RGB}}{{166,186,208}}
\definecolor{{coversoft}}{{RGB}}{{227,236,245}}
\definecolor{{coverline}}{{RGB}}{{151,171,194}}
\definecolor{{coverink}}{{RGB}}{{42,58,74}}
\color{{worksheetink}}
\setstretch{{1.03}}
\setlength{{\parskip}}{{2.2pt}}
\pagestyle{{fancy}}
\fancyhf{{}}
\IfFileExists{{fontawesome5.sty}}{{%
  \usepackage{{fontawesome5}}
  \newcommand{{\headerbook}}{{\faBookOpen}}
}}{{%
  \newcommand{{\headerbook}}{{\raisebox{{0.1ex}}{{\small$\square$}}}}
}}
\fancyhead[L]{{\normalsize\bfseries {header_brand}}}
\fancyhead[R]{{\normalsize\bfseries \headerbook\ {header_title} · \leftmark}}
\fancyfoot[C]{{\normalsize · 第 \thepage 页，共 \pageref{{LastPage}} 页 ·}}
\renewcommand{{\headrulewidth}}{{0.4pt}}
\renewcommand{{\footrulewidth}}{{0pt}}
\fancypagestyle{{plain}}{{%
  \fancyhf{{}}
  \fancyhead[L]{{\normalsize\bfseries {header_brand}}}
  \fancyhead[R]{{\normalsize\bfseries \headerbook\ {header_title} · \leftmark}}
  \fancyfoot[C]{{\normalsize · 第 \thepage 页，共 \pageref{{LastPage}} 页 ·}}
  \renewcommand{{\headrulewidth}}{{0.4pt}}
  \renewcommand{{\footrulewidth}}{{0pt}}
}}
\renewcommand{{\contentsname}}{{目录}}
\setcounter{{tocdepth}}{{1}}
\setlength{{\cftbeforesecskip}}{{0.95em}}
\setlength{{\cftsecindent}}{{0pt}}
\setlength{{\cftsecnumwidth}}{{0pt}}
\renewcommand{{\cfttoctitlefont}}{{\hfill\fontsize{{22}}{{26}}\selectfont\bfseries}}
\renewcommand{{\cftaftertoctitle}}{{\hfill\mbox{{}}\par\vspace{{0.7em}}\color{{coverline}}\hrule height 0.6pt\par\vspace{{1.0em}}}}
\renewcommand{{\cftsecfont}}{{\normalsize}}
\renewcommand{{\cftsecpagefont}}{{\normalsize\bfseries}}
\renewcommand{{\cftsecleader}}{{\cftdotfill{{\cftdotsep}}}}
\renewcommand{{\cftdotsep}}{{1.2}}

\newcommand{{\makeworkbookcover}}{{%
  \begin{{titlepage}}
  \thispagestyle{{empty}}
  \color{{worksheetink}}
  \begin{{tikzpicture}}[remember picture,overlay]
    \fill[coverbg] (current page.north west) rectangle (current page.south east);
    \shade[top color=coverbarlight,bottom color=coverbardark]
      ([xshift=-4.8cm]current page.north east) rectangle (current page.south east);
    \fill[coversoft,opacity=0.9] ([xshift=1.55cm,yshift=1.8cm]current page.south west) circle (3.3cm);
    \draw[coverline,line width=0.7pt,opacity=0.7] ([xshift=5.55cm,yshift=3.25cm]current page.south west) circle (1.0cm);
    \fill[white,opacity=0.4] ([xshift=-0.95cm,yshift=-0.9cm]current page.north east) circle (2.45cm);
    \node[anchor=north west,text=coveraccent,font=\fontsize{{9}}{{11}}\selectfont] at ([xshift=1.5cm,yshift=-1.75cm]current page.north west) {{{small_label}}};
{cover_image}
    \node[anchor=north west,text=white,font=\bfseries\fontsize{{12}}{{15}}\selectfont] at ([xshift=-3.95cm,yshift=-1.8cm]current page.north east) {{{header_brand}}};
    \draw[white,line width=0.7pt] ([xshift=-3.95cm,yshift=-2.65cm]current page.north east) -- ([xshift=-3.35cm,yshift=-2.65cm]current page.north east);
    \node[anchor=north west,text=white,font=\fontsize{{8}}{{10}}\selectfont,align=left] at ([xshift=-3.95cm,yshift=-3.15cm]current page.north east) {{FOCUS\\LEARN\\GROW}};
    \draw[white,line width=0.7pt] ([xshift=-3.55cm,yshift=7.25cm]current page.south east) -- ([xshift=-3.55cm,yshift=4.05cm]current page.south east);
    \node[anchor=south west,text=white,font=\fontsize{{9}}{{11}}\selectfont] at ([xshift=-3.75cm,yshift=2.8cm]current page.south east) {{NOTEBOOK}};
    \draw[white,line width=0.7pt] ([xshift=-3.75cm,yshift=2.45cm]current page.south east) -- ([xshift=-3.25cm,yshift=2.45cm]current page.south east);
    \node[anchor=south west,text=white,font=\fontsize{{8}}{{10}}\selectfont] at ([xshift=-3.75cm,yshift=1.85cm]current page.south east) {{专注 · 学习 · 成长}};
    \fill[white,opacity=0.85] ([xshift=-3.55cm,yshift=1.02cm]current page.south east) circle (0.05cm);
    \fill[white,opacity=0.85] ([xshift=-3.18cm,yshift=1.02cm]current page.south east) circle (0.05cm);
    \fill[white,opacity=0.85] ([xshift=-2.81cm,yshift=1.02cm]current page.south east) circle (0.05cm);
    \node[anchor=north west,fill=coverink,text=white,rounded corners=4pt,inner xsep=12pt,inner ysep=7pt,font=\bfseries\small] at ([xshift=1.8cm,yshift=-13.45cm]current page.north west) {{{variant_label}}};
    \draw[coverline,opacity=0.35,line width=0.4pt] ([xshift=9.2cm,yshift=11.05cm]current page.south west) -- ([xshift=14.8cm,yshift=11.05cm]current page.south west);
    \draw[coverline,opacity=0.35,line width=0.4pt] ([xshift=9.2cm,yshift=10.55cm]current page.south west) -- ([xshift=14.8cm,yshift=10.55cm]current page.south west);
    \draw[coverline,opacity=0.35,line width=0.4pt] ([xshift=9.2cm,yshift=10.05cm]current page.south west) -- ([xshift=14.8cm,yshift=10.05cm]current page.south west);
    \draw[coverline,opacity=0.35,line width=0.4pt] ([xshift=9.2cm,yshift=9.55cm]current page.south west) -- ([xshift=14.8cm,yshift=9.55cm]current page.south west);
    \draw[coverline,opacity=0.35,line width=0.4pt] ([xshift=9.2cm,yshift=9.05cm]current page.south west) -- ([xshift=14.8cm,yshift=9.05cm]current page.south west);
    \draw[coverline,opacity=0.35,line width=0.4pt] ([xshift=9.2cm,yshift=8.55cm]current page.south west) -- ([xshift=14.8cm,yshift=8.55cm]current page.south west);
    \draw[coverline,opacity=0.35,line width=0.4pt] ([xshift=9.2cm,yshift=8.05cm]current page.south west) -- ([xshift=14.8cm,yshift=8.05cm]current page.south west);
    \draw[coverline,opacity=0.5,line width=1.2pt] ([xshift=13.8cm,yshift=11.25cm]current page.south west) -- ([xshift=15.2cm,yshift=11.0cm]current page.south west);
    \fill[coversoft,opacity=0.55] ([xshift=14.8cm,yshift=8.9cm]current page.south west) rectangle ([xshift=15.8cm,yshift=9.9cm]current page.south west);
    \begin{{scope}}[shift={{([xshift=2.25cm,yshift=9.8cm]current page.south west)}}]
      \foreach \x in {{0,...,8}} {{
        \foreach \y in {{0,...,8}} {{
          \fill[coveraccent,opacity=0.45] (\x*0.27cm,\y*0.27cm) circle (0.024cm);
        }}
      }}
    \end{{scope}}
    \node[anchor=north west,text=coverink,align=left,text width=7.6cm,font=\bfseries\fontsize{{31}}{{36}}\selectfont]
      at ([xshift=1.8cm,yshift=-3.35cm]current page.north west) {{{cover_title_main}}};
    """ + (rf"""
    \node[anchor=north west,text=covermuted,align=left,font=\bfseries\fontsize{{23}}{{28}}\selectfont]
      at ([xshift=1.8cm,yshift=-5.65cm]current page.north west) {{{cover_title_edition}}};
    """ if cover_title_edition else "") + rf"""
    \node[anchor=north west,text=covermuted,align=left,font=\bfseries\fontsize{{17}}{{22}}\selectfont]
      at ([xshift=1.8cm,yshift=-7.85cm]current page.north west) {{{subtitle}}};
    \draw[coverline,line width=0.9pt] ([xshift=1.8cm,yshift=-9.55cm]current page.north west) -- ([xshift=8.95cm,yshift=-9.55cm]current page.north west);
    \node[anchor=north west,text=coverink,align=left,font=\bfseries\fontsize{{10.5}}{{13}}\selectfont]
      at ([xshift=1.8cm,yshift=-10.45cm]current page.north west) {{{tagline}}};
  \end{{tikzpicture}}
  \end{{titlepage}}
  \clearpage
  \setcounter{{page}}{{1}}
}}
\newcommand{{\makeworkbooktoc}}{{%
  \markboth{{目录}}{{目录}}%
  \renewcommand{{\contentsname}}{{目录}}%
  \tableofcontents
  \clearpage
}}
\newif\ifworkbookcover
\newif\ifworkbooktoc
{workbook_cover_flag}
{workbook_toc_flag}

\newcommand{{\worksheetchapter}}[1]{{%
  \markboth{{#1}}{{#1}}%
  \addcontentsline{{toc}}{{section}}{{#1}}%
  \par\medskip
  \noindent{{\large\bfseries #1}}\par
  \vspace{{0.45em}}
}}
\newcommand{{\problemnumber}}[1]{{%
  \par\smallskip
  \noindent{{\normalsize\bfseries #1}}\par
  \vspace{{0.25em}}
  \normalsize
}}

\begin{{document}}
\ifworkbookcover\makeworkbookcover\fi
\ifworkbooktoc\makeworkbooktoc\fi
\input{{{body_name}}}
\end{{document}}
""".strip() + "\n"


def build_spaced_tex(
    book_title: str,
    brand: str,
    body_name: str,
    question_count: int,
    chapter_count: int,
    include_cover: bool,
    include_toc: bool,
    cover_image_rel: str | None,
) -> str:
    header_title = tex_escape(book_title or "做题本")
    header_brand = tex_escape(brand or DEFAULT_BRAND)
    variant_label = tex_escape("留白版")
    cover_title_main_raw, cover_title_edition_raw = split_book_title_for_cover(book_title or "做题本")
    cover_title_main = tex_escape(cover_title_main_raw)
    cover_title_edition = tex_escape(cover_title_edition_raw) if cover_title_edition_raw else ""
    edition_block = (
        rf"{{\fontsize{{22}}{{27}}\selectfont\bfseries\color{{covermuted}} {cover_title_edition}\par}}"
        if cover_title_edition
        else ""
    )
    small_label = tex_escape(infer_cover_english_label(book_title or "做题本"))
    subtitle = tex_escape("做题本")
    tagline = tex_escape("一页一题排版 · 适合书写打印")
    cover_image = build_cover_image_snippet(cover_image_rel)
    workbook_cover_flag = r"\workbookcovertrue" if include_cover else r"\workbookcoverfalse"
    workbook_toc_flag = r"\workbooktoctrue" if include_toc else r"\workbooktocfalse"
    return rf"""
\documentclass[10pt,a4paper,fontset=none]{{ctexart}}
\usepackage[top=1.65cm,bottom=1.55cm,left=2.55cm,right=2.55cm,headheight=16pt,headsep=4pt,footskip=18pt]{{geometry}}
{COMMON_PREAMBLE}

\definecolor{{worksheetline}}{{RGB}}{{80,80,80}}
\definecolor{{worksheetink}}{{RGB}}{{18,18,18}}
\definecolor{{worksheetmuted}}{{RGB}}{{70,70,70}}
\definecolor{{coverbg}}{{RGB}}{{251,250,247}}
\definecolor{{coverbarlight}}{{RGB}}{{200,214,228}}
\definecolor{{coverbardark}}{{RGB}}{{150,169,191}}
\definecolor{{coveraccent}}{{RGB}}{{112,137,166}}
\definecolor{{covermuted}}{{RGB}}{{166,186,208}}
\definecolor{{coversoft}}{{RGB}}{{227,236,245}}
\definecolor{{coverline}}{{RGB}}{{151,171,194}}
\definecolor{{coverink}}{{RGB}}{{42,58,74}}
\color{{worksheetink}}
\setstretch{{1.05}}
\setlength{{\parskip}}{{2.8pt}}
\pagestyle{{fancy}}
\fancyhf{{}}
\IfFileExists{{fontawesome5.sty}}{{%
  \usepackage{{fontawesome5}}
  \newcommand{{\headerbook}}{{\faBookOpen}}
}}{{%
  \newcommand{{\headerbook}}{{\raisebox{{0.1ex}}{{\small$\square$}}}}
}}
\fancyhead[L]{{\normalsize\bfseries {header_brand}}}
\fancyhead[R]{{\normalsize\bfseries \headerbook\ {header_title} · \leftmark}}
\fancyfoot[C]{{\normalsize · 第 \thepage 页，共 \pageref{{LastPage}} 页 ·}}
\renewcommand{{\headrulewidth}}{{0.4pt}}
\renewcommand{{\footrulewidth}}{{0pt}}
\fancypagestyle{{plain}}{{%
  \fancyhf{{}}
  \fancyhead[L]{{\normalsize\bfseries {header_brand}}}
  \fancyhead[R]{{\normalsize\bfseries \headerbook\ {header_title} · \leftmark}}
  \fancyfoot[C]{{\normalsize · 第 \thepage 页，共 \pageref{{LastPage}} 页 ·}}
  \renewcommand{{\headrulewidth}}{{0.4pt}}
  \renewcommand{{\footrulewidth}}{{0pt}}
}}
\renewcommand{{\contentsname}}{{目录}}
\setcounter{{tocdepth}}{{1}}
\setlength{{\cftbeforesecskip}}{{0.95em}}
\setlength{{\cftsecindent}}{{0pt}}
\setlength{{\cftsecnumwidth}}{{0pt}}
\renewcommand{{\cfttoctitlefont}}{{\hfill\fontsize{{22}}{{26}}\selectfont\bfseries}}
\renewcommand{{\cftaftertoctitle}}{{\hfill\mbox{{}}\par\vspace{{0.7em}}\color{{coverline}}\hrule height 0.6pt\par\vspace{{1.0em}}}}
\renewcommand{{\cftsecfont}}{{\normalsize}}
\renewcommand{{\cftsecpagefont}}{{\normalsize\bfseries}}
\renewcommand{{\cftsecleader}}{{\cftdotfill{{\cftdotsep}}}}
\renewcommand{{\cftdotsep}}{{1.2}}

\newcommand{{\makeworkbookcover}}{{%
  \begin{{titlepage}}
  \thispagestyle{{empty}}
  \color{{worksheetink}}
  \begin{{tikzpicture}}[remember picture,overlay]
    \fill[coverbg] (current page.north west) rectangle (current page.south east);
    \shade[top color=coverbarlight,bottom color=coverbardark]
      ([xshift=-4.8cm]current page.north east) rectangle (current page.south east);
    \fill[coversoft,opacity=0.9] ([xshift=1.55cm,yshift=1.8cm]current page.south west) circle (3.3cm);
    \draw[coverline,line width=0.7pt,opacity=0.7] ([xshift=5.55cm,yshift=3.25cm]current page.south west) circle (1.0cm);
    \fill[white,opacity=0.4] ([xshift=-0.95cm,yshift=-0.9cm]current page.north east) circle (2.45cm);
    \node[anchor=north west,text=coveraccent,font=\fontsize{{9}}{{11}}\selectfont] at ([xshift=1.5cm,yshift=-1.75cm]current page.north west) {{{small_label}}};
{cover_image}
    \node[anchor=north west,text=white,font=\bfseries\fontsize{{12}}{{15}}\selectfont] at ([xshift=-3.95cm,yshift=-1.8cm]current page.north east) {{{header_brand}}};
    \draw[white,line width=0.7pt] ([xshift=-3.95cm,yshift=-2.65cm]current page.north east) -- ([xshift=-3.35cm,yshift=-2.65cm]current page.north east);
    \node[anchor=north west,text=white,font=\fontsize{{8}}{{10}}\selectfont,align=left] at ([xshift=-3.95cm,yshift=-3.15cm]current page.north east) {{FOCUS\\LEARN\\GROW}};
    \draw[white,line width=0.7pt] ([xshift=-3.55cm,yshift=7.25cm]current page.south east) -- ([xshift=-3.55cm,yshift=4.05cm]current page.south east);
    \node[anchor=south west,text=white,font=\fontsize{{9}}{{11}}\selectfont] at ([xshift=-3.75cm,yshift=2.8cm]current page.south east) {{NOTEBOOK}};
    \draw[white,line width=0.7pt] ([xshift=-3.75cm,yshift=2.45cm]current page.south east) -- ([xshift=-3.25cm,yshift=2.45cm]current page.south east);
    \node[anchor=south west,text=white,font=\fontsize{{8}}{{10}}\selectfont] at ([xshift=-3.75cm,yshift=1.85cm]current page.south east) {{专注 · 学习 · 成长}};
    \fill[white,opacity=0.85] ([xshift=-3.55cm,yshift=1.02cm]current page.south east) circle (0.05cm);
    \fill[white,opacity=0.85] ([xshift=-3.18cm,yshift=1.02cm]current page.south east) circle (0.05cm);
    \fill[white,opacity=0.85] ([xshift=-2.81cm,yshift=1.02cm]current page.south east) circle (0.05cm);
    \node[anchor=north west,fill=coverink,text=white,rounded corners=4pt,inner xsep=12pt,inner ysep=7pt,font=\bfseries\small] at ([xshift=1.8cm,yshift=-13.45cm]current page.north west) {{{variant_label}}};
    \draw[coverline,opacity=0.35,line width=0.4pt] ([xshift=9.2cm,yshift=11.05cm]current page.south west) -- ([xshift=14.8cm,yshift=11.05cm]current page.south west);
    \draw[coverline,opacity=0.35,line width=0.4pt] ([xshift=9.2cm,yshift=10.55cm]current page.south west) -- ([xshift=14.8cm,yshift=10.55cm]current page.south west);
    \draw[coverline,opacity=0.35,line width=0.4pt] ([xshift=9.2cm,yshift=10.05cm]current page.south west) -- ([xshift=14.8cm,yshift=10.05cm]current page.south west);
    \draw[coverline,opacity=0.35,line width=0.4pt] ([xshift=9.2cm,yshift=9.55cm]current page.south west) -- ([xshift=14.8cm,yshift=9.55cm]current page.south west);
    \draw[coverline,opacity=0.35,line width=0.4pt] ([xshift=9.2cm,yshift=9.05cm]current page.south west) -- ([xshift=14.8cm,yshift=9.05cm]current page.south west);
    \draw[coverline,opacity=0.35,line width=0.4pt] ([xshift=9.2cm,yshift=8.55cm]current page.south west) -- ([xshift=14.8cm,yshift=8.55cm]current page.south west);
    \draw[coverline,opacity=0.35,line width=0.4pt] ([xshift=9.2cm,yshift=8.05cm]current page.south west) -- ([xshift=14.8cm,yshift=8.05cm]current page.south west);
    \draw[coverline,opacity=0.5,line width=1.2pt] ([xshift=13.8cm,yshift=11.25cm]current page.south west) -- ([xshift=15.2cm,yshift=11.0cm]current page.south west);
    \fill[coversoft,opacity=0.55] ([xshift=14.8cm,yshift=8.9cm]current page.south west) rectangle ([xshift=15.8cm,yshift=9.9cm]current page.south west);
    \begin{{scope}}[shift={{([xshift=2.25cm,yshift=9.8cm]current page.south west)}}]
      \foreach \x in {{0,...,8}} {{
        \foreach \y in {{0,...,8}} {{
          \fill[coveraccent,opacity=0.45] (\x*0.27cm,\y*0.27cm) circle (0.024cm);
        }}
      }}
    \end{{scope}}
    \node[anchor=north west,text=coverink,align=left,text width=7.6cm,font=\bfseries\fontsize{{31}}{{36}}\selectfont]
      at ([xshift=1.8cm,yshift=-3.35cm]current page.north west) {{{cover_title_main}}};
    """ + (rf"""
    \node[anchor=north west,text=covermuted,align=left,font=\bfseries\fontsize{{23}}{{28}}\selectfont]
      at ([xshift=1.8cm,yshift=-5.65cm]current page.north west) {{{cover_title_edition}}};
    """ if cover_title_edition else "") + rf"""
    \node[anchor=north west,text=covermuted,align=left,font=\bfseries\fontsize{{17}}{{22}}\selectfont]
      at ([xshift=1.8cm,yshift=-7.85cm]current page.north west) {{{subtitle}}};
    \draw[coverline,line width=0.9pt] ([xshift=1.8cm,yshift=-9.55cm]current page.north west) -- ([xshift=8.95cm,yshift=-9.55cm]current page.north west);
    \node[anchor=north west,text=coverink,align=left,font=\bfseries\fontsize{{10.5}}{{13}}\selectfont]
      at ([xshift=1.8cm,yshift=-10.45cm]current page.north west) {{{tagline}}};
  \end{{tikzpicture}}
  \end{{titlepage}}
  \clearpage
  \setcounter{{page}}{{1}}
}}
\newcommand{{\makeworkbooktoc}}{{%
  \markboth{{目录}}{{目录}}%
  \renewcommand{{\contentsname}}{{目录}}%
  \tableofcontents
  \clearpage
}}
\newif\ifworkbookcover
\newif\ifworkbooktoc
{workbook_cover_flag}
{workbook_toc_flag}

\newcommand{{\worksheetchapter}}[1]{{%
  \markboth{{#1}}{{#1}}%
  \addcontentsline{{toc}}{{section}}{{#1}}%
}}
\newcommand{{\problemnumber}}[1]{{%
  \vspace*{{0em}}
  \noindent{{\normalsize\bfseries #1}}\par
  \vspace{{0.4em}}
  \normalsize
}}
\newcommand{{\problemend}}{{%
  \par\vfill\newpage
}}
\newcommand{{\problemlast}}{{%
  \par\vfill
}}

\begin{{document}}
\ifworkbookcover\makeworkbookcover\fi
\ifworkbooktoc\makeworkbooktoc\fi
\input{{{body_name}}}
\end{{document}}
""".strip() + "\n"


def normalize_input_paths(paths: list[str]) -> list[Path]:
    resolved: list[Path] = []
    for raw in paths:
        path = Path(raw).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"输入路径不存在: {path}")
        resolved.append(path)
    return resolved


def discover_files(inputs: list[Path], suffix: str) -> list[Path]:
    suffix = suffix.lower()
    files: list[Path] = []
    seen: set[Path] = set()
    for path in inputs:
        candidates = [path] if path.is_file() else sorted(path.rglob(f"*{suffix}"))
        for candidate in candidates:
            if candidate.suffix.lower() != suffix:
                continue
            if any(part in IGNORED_DIR_NAMES for part in candidate.parts):
                continue
            if candidate in seen:
                continue
            seen.add(candidate)
            files.append(candidate)
    return files


def discover_tex_files(inputs: list[Path], required: bool = True) -> list[Path]:
    tex_files: list[Path] = []
    seen: set[Path] = set()
    for path in inputs:
        candidates = [path] if path.is_file() else sorted(path.rglob("*.tex"))
        for candidate in candidates:
            if candidate.suffix.lower() != ".tex":
                continue
            if any(part in IGNORED_DIR_NAMES for part in candidate.parts):
                continue
            if candidate.name.endswith(("_compact.tex", "_one_problem_per_page.tex", "_compact_body.tex", "_one_problem_per_page_body.tex")):
                continue
            if candidate in seen:
                continue
            seen.add(candidate)
            tex_files.append(candidate)
    if required and not tex_files:
        raise FileNotFoundError("没有找到任何 .tex 文件")
    return tex_files


def discover_pdf_files(inputs: list[Path]) -> list[Path]:
    return discover_files(inputs, ".pdf")


def discover_markdown_files(inputs: list[Path]) -> list[Path]:
    return [*discover_files(inputs, ".md"), *discover_files(inputs, ".markdown")]


def resolve_mineru_launcher() -> list[str]:
    candidates = [
        shutil.which("mineru-open-api"),
        shutil.which("mineru-open-api.cmd"),
        shutil.which("mineru-open-api.exe"),
        shutil.which("mineru-open-api.ps1"),
    ]
    launcher = next((item for item in candidates if item), None)
    if launcher is None:
        raise FileNotFoundError("未找到 mineru-open-api 命令。")

    path = Path(launcher)
    suffix = path.suffix.lower()
    if suffix == ".ps1":
        return [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(path),
        ]
    return [str(path)]


def run_mineru_extract(
    pdf_files: list[Path],
    out_dir: Path,
    formats: list[str],
    model: str,
    language: str,
    timeout: int,
    pages: str | None,
) -> list[str]:
    issues: list[str] = []
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        mineru_base_cmd = resolve_mineru_launcher()
    except FileNotFoundError as exc:
        return [str(exc)]
    for pdf_file in pdf_files:
        for fmt in formats:
            cmd = [
                *mineru_base_cmd,
                "extract",
                str(pdf_file),
                "-o",
                str(out_dir),
                "-f",
                fmt,
                "--model",
                model,
                "--ocr",
                "--formula",
                "--table",
                "--language",
                language,
                "--timeout",
                str(timeout),
            ]
            if pages:
                cmd.extend(["--pages", pages])
            result = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if result.returncode != 0:
                output = "\n".join(
                    part.strip() for part in (result.stdout, result.stderr) if part.strip()
                )
                tail = "\n".join(output.splitlines()[-20:]) if output else "无可用日志。"
                issues.append(f"MinerU {fmt} 提取失败: {pdf_file.name}\n{tail}")
    return issues


def parse_heading_at(lines: list[str], start: int) -> tuple[Heading, int] | None:
    match = HEADING_OPEN_RE.match(lines[start])
    if match is None:
        return None

    command = match.group("cmd")
    current_line = start
    current_text = lines[start][match.end() :]
    chars: list[str] = []
    depth = 1
    index = 0

    while True:
        while index < len(current_text):
            char = current_text[index]
            if char == "{":
                depth += 1
                chars.append(char)
            elif char == "}":
                depth -= 1
                if depth == 0:
                    title = "".join(chars).strip()
                    return (
                        Heading(
                            command=command,
                            level=HEADING_LEVELS[command],
                            title=title,
                            line_start=start,
                            line_end=current_line + 1,
                        ),
                        current_line + 1,
                    )
                chars.append(char)
            else:
                chars.append(char)
            index += 1

        current_line += 1
        if current_line >= len(lines):
            break
        chars.append("\n")
        current_text = lines[current_line]
        index = 0
    return None


def parse_headings(lines: list[str]) -> list[Heading]:
    headings: list[Heading] = []
    index = 0
    while index < len(lines):
        parsed = parse_heading_at(lines, index)
        if parsed is None:
            index += 1
            continue
        heading, next_index = parsed
        headings.append(heading)
        index = next_index
    return headings


def is_exercise_heading(title: str, exercise_keywords: list[str], exclude_keywords: list[str]) -> bool:
    lowered = title.casefold()
    if any(keyword.casefold() in lowered for keyword in exclude_keywords):
        return False
    return any(keyword.casefold() in lowered for keyword in exercise_keywords)


def is_plain_chapter_title_candidate(title: str, exercise_keywords: list[str], exclude_keywords: list[str]) -> bool:
    if not title or len(title) > 40:
        return False
    if looks_like_numbered_heading(title):
        return False
    if is_exercise_heading(title, exercise_keywords, exclude_keywords):
        return False
    lowered = title.casefold()
    disallowed = ("目录", "出版说明", "参考文献", "作者索引", "名词索引", "附录")
    return not any(item.casefold() in lowered for item in disallowed)


def extract_numeric_key(title: str) -> tuple[int, ...] | None:
    normalized = normalize_heading_title(title)
    decimal_match = LEADING_DECIMAL_RE.match(normalized)
    if decimal_match:
        return tuple(int(part) for part in decimal_match.group("num").split("."))

    chapter_match = CHAPTER_ONLY_RE.match(normalized) or CHAPTER_FULL_RE.match(normalized)
    if chapter_match:
        number = parse_cn_number(chapter_match.group("num"))
        if number is not None:
            return (number,)
    return None


def derive_fallback_context(section_title: str) -> ChapterContext:
    numeric_key = extract_numeric_key(section_title)
    if numeric_key:
        number = numeric_key[0]
        return ChapterContext(label=f"第{number}章", number=number)
    return ChapterContext(title=section_title)


def update_context_from_heading(
    context: ChapterContext,
    title: str,
    exercise_keywords: list[str],
    exclude_keywords: list[str],
) -> ChapterContext:
    chapter_full = CHAPTER_FULL_RE.match(title)
    if chapter_full:
        label = f"第{chapter_full.group('num')}章"
        return ChapterContext(
            label=label,
            number=parse_cn_number(chapter_full.group("num")),
            title=normalize_heading_title(chapter_full.group("title")),
        )

    chapter_only = CHAPTER_ONLY_RE.match(title)
    if chapter_only:
        label = f"第{chapter_only.group('num')}章"
        return ChapterContext(
            label=label,
            number=parse_cn_number(chapter_only.group("num")),
            title=None,
        )

    if context.label and context.title is None and is_plain_chapter_title_candidate(
        title, exercise_keywords, exclude_keywords
    ):
        return ChapterContext(label=context.label, number=context.number, title=title)

    return context


def copy_images(lines: list[str], source_dir: Path, out_dir: Path) -> None:
    for line in lines:
        for match in INCLUDEGRAPHICS_RE.finditer(line):
            raw_path = match.group("path").strip()
            if not raw_path or raw_path.startswith(("http://", "https://")):
                continue
            rel_path = Path(raw_path)
            if rel_path.is_absolute():
                continue
            source_path = source_dir / rel_path
            target_path = out_dir / rel_path
            if not source_path.exists():
                continue
            target_path.parent.mkdir(parents=True, exist_ok=True)
            if not target_path.exists():
                shutil.copy2(source_path, target_path)


def clean_section_lines(lines: list[str]) -> list[str]:
    cleaned: list[str] = []
    index = 0
    enum_stack: list[dict[str, int | bool | str]] = []
    while index < len(lines):
        stripped = lines[index].strip()
        if stripped == r"\end{document}":
            break
        if stripped in {r"\begin{document}", r"\maketitle"}:
            index += 1
            continue
        if stripped.startswith(r"\begin{enumerate}"):
            enum_stack.append({"counter": 0, "numbered": False, "name": "enumi"})
            index += 1
            continue
        if stripped.startswith(r"\end{enumerate}"):
            if enum_stack:
                enum_stack.pop()
            index += 1
            continue
        if stripped == r"\tightlist":
            index += 1
            continue
        counter_match = ENUM_COUNTER_RE.search(stripped)
        if counter_match and enum_stack:
            enum_stack[-1]["counter"] = int(counter_match.group("value"))
            enum_stack[-1]["name"] = counter_match.group("name")
            index += 1
            continue
        label_match = LABEL_ENUM_RE.search(stripped)
        if label_match and enum_stack:
            enum_stack[-1]["numbered"] = True
            enum_stack[-1]["name"] = label_match.group("name")
            index += 1
            continue

        parsed = parse_heading_at(lines, index)
        if parsed is not None:
            heading, next_index = parsed
            heading_title = normalize_heading_title(heading.title)
            cleaned.append(rf"\exerciseheading{{{heading_title}}}")
            index = next_index
            continue

        line = LABEL_RE.sub("", lines[index]).rstrip()
        item_match = ITEM_RE.match(line)
        if item_match and enum_stack:
            enum_state = enum_stack[-1]
            enum_state["counter"] = int(enum_state.get("counter", 0)) + 1
            rest = item_match.group("rest").strip()
            marker = format_alpha_enum(int(enum_state["counter"]))
            line = f"{marker} {rest}".rstrip()
        cleaned.append(line)
        index += 1
    return cleaned


def collect_exercise_sections(
    tex_files: list[Path],
    out_dir: Path,
    exercise_keywords: list[str],
    exclude_keywords: list[str],
    question_patterns: list[re.Pattern[str]],
) -> tuple[list[ExerciseSection], list[Heading], list[str]]:
    sections: list[ExerciseSection] = []
    all_headings: list[Heading] = []
    issues: list[str] = []

    for source_order, tex_file in enumerate(tex_files):
        source_lines = tex_file.read_text(encoding="utf-8").splitlines()
        headings = parse_headings(source_lines)
        all_headings.extend(headings)

        context = ChapterContext()
        for heading_order, heading in enumerate(headings):
            title = normalize_heading_title(heading.title)
            context = update_context_from_heading(
                context, title, exercise_keywords, exclude_keywords
            )
            if not is_exercise_heading(title, exercise_keywords, exclude_keywords):
                continue

            end_line = len(source_lines)
            for next_heading in headings[heading_order + 1 :]:
                if next_heading.level > heading.level:
                    continue
                next_title = normalize_heading_title(next_heading.title)
                if is_exercise_heading(next_title, exercise_keywords, exclude_keywords):
                    end_line = next_heading.line_start
                    break
                if CHAPTER_ONLY_RE.match(next_title) or CHAPTER_FULL_RE.match(next_title):
                    end_line = next_heading.line_start
                    break
                if any(keyword.casefold() in next_title.casefold() for keyword in exclude_keywords):
                    end_line = next_heading.line_start
                    break
                if match_question_start(next_title, question_patterns) is not None:
                    continue
                if extract_numeric_key(next_title) is not None:
                    end_line = next_heading.line_start
                    break

            raw_lines = source_lines[heading.line_end : end_line]
            if not any(line.strip() for line in raw_lines):
                issues.append(f"{tex_file.name} 中的习题节为空: {title}")
                continue

            copy_images(raw_lines, tex_file.parent, out_dir)
            cleaned_lines = clean_section_lines(raw_lines)

            section_context = context if context.display else derive_fallback_context(title)
            chapter_display = section_context.display or title
            chapter_key = chapter_display or f"section-{source_order}-{heading_order}"
            numeric_key = extract_numeric_key(title)
            if numeric_key is not None:
                sort_bucket = 0
            elif section_context.number is not None:
                numeric_key = (section_context.number,)
                sort_bucket = 1
            else:
                numeric_key = (source_order + 1, heading_order + 1)
                sort_bucket = 2

            sections.append(
                ExerciseSection(
                    chapter_key=chapter_key,
                    chapter_display=chapter_display,
                    section_title=title,
                    lines=cleaned_lines,
                    sort_bucket=sort_bucket,
                    numeric_key=numeric_key,
                    source_order=source_order,
                    heading_order=heading_order,
                )
            )

    sections.sort(
        key=lambda item: (
            item.sort_bucket,
            item.numeric_key,
            item.source_order,
            item.heading_order,
        )
    )
    return sections, all_headings, issues


def read_exercise_heading(lines: list[str], start: int) -> tuple[str, int]:
    parts = [lines[start][len(r"\exerciseheading{") :]]
    index = start
    while "}" not in parts[-1]:
        index += 1
        parts.append(lines[index])
    tail, _, _ = parts[-1].partition("}")
    parts[-1] = tail
    heading = "\n".join(parts).strip()
    return heading, index + 1


def compile_question_patterns(extra_patterns: list[str]) -> list[re.Pattern[str]]:
    patterns: list[re.Pattern[str]] = []
    for raw_pattern in [*DEFAULT_QUESTION_PATTERNS, *extra_patterns]:
        pattern = re.compile(raw_pattern, re.S)
        if "num" not in pattern.groupindex:
            raise ValueError(f"题号正则缺少命名组 num: {raw_pattern}")
        patterns.append(pattern)
    return patterns


def match_question_start(
    text: str, question_patterns: list[re.Pattern[str]]
) -> tuple[str, str] | None:
    stripped = text.strip()
    for pattern in question_patterns:
        match = pattern.match(stripped)
        if match is None:
            continue
        number = match.group("num").strip()
        rest = match.groupdict().get("rest", "") or ""
        return number, rest.strip()
    return None


def parse_question_start(
    lines: list[str], start: int, question_patterns: list[re.Pattern[str]]
) -> tuple[str, list[str], int] | None:
    line = lines[start]

    if line.startswith(r"\exerciseheading{"):
        heading, next_index = read_exercise_heading(lines, start)
        matched = match_question_start(heading, question_patterns)
        if matched is None:
            return None
        number, rest = matched
        return number, [rest] if rest else [], next_index

    matched = match_question_start(line, question_patterns)
    if matched is None:
        return None
    number, rest = matched
    return number, [rest] if rest else [], start + 1


def parse_questions(
    sections: list[ExerciseSection], question_patterns: list[re.Pattern[str]]
) -> tuple[list[Question], list[str]]:
    questions: list[Question] = []
    issues: list[str] = []

    for section in sections:
        current_number: str | None = None
        current_lines: list[str] = []
        env_depth = 0
        display_depth = 0
        parsed_in_section = 0

        index = 0
        while index < len(section.lines):
            can_start_new = current_number is None or (env_depth == 0 and display_depth == 0)

            if can_start_new and section.lines[index].startswith(r"\exerciseheading{"):
                heading, next_index = read_exercise_heading(section.lines, index)
                if match_question_start(heading, question_patterns) is None:
                    if current_number is None:
                        issues.append(
                            f"{section.chapter_display} 的习题节首部有未识别小标题: {heading[:40]}"
                        )
                    else:
                        current_lines.append(rf"\textbf{{{heading}}}")
                        current_lines.append("")
                    index = next_index
                    continue

            start_info = (
                parse_question_start(section.lines, index, question_patterns)
                if can_start_new
                else None
            )
            if start_info is not None:
                if current_number is not None:
                    questions.append(
                        Question(
                            chapter_key=section.chapter_key,
                            chapter_display=section.chapter_display,
                            number=current_number,
                            lines=current_lines.copy(),
                        )
                    )
                    parsed_in_section += 1

                current_number, initial_lines, index = start_info
                current_lines = initial_lines.copy()
                env_depth = 0
                display_depth = 0
                for line in current_lines:
                    env_depth += line.count(r"\begin{") - line.count(r"\end{")
                    display_depth += line.count(r"\[") - line.count(r"\]")
                env_depth = max(env_depth, 0)
                display_depth = max(display_depth, 0)
                continue

            if current_number is None:
                index += 1
                continue

            current_lines.append(section.lines[index])
            env_depth += section.lines[index].count(r"\begin{") - section.lines[index].count(r"\end{")
            display_depth += section.lines[index].count(r"\[") - section.lines[index].count(r"\]")
            env_depth = max(env_depth, 0)
            display_depth = max(display_depth, 0)
            index += 1

        if current_number is not None:
            questions.append(
                Question(
                    chapter_key=section.chapter_key,
                    chapter_display=section.chapter_display,
                    number=current_number,
                    lines=current_lines.copy(),
                )
            )
            parsed_in_section += 1

        if parsed_in_section == 0:
            issues.append(f"{section.chapter_display} 未解析出题目，请考虑补充 --question-pattern")

    return questions, issues


def trim_problem_lines(lines: list[str]) -> list[str]:
    trimmed = lines.copy()
    while trimmed and not trimmed[0].strip():
        trimmed.pop(0)
    while trimmed and not trimmed[-1].strip():
        trimmed.pop()
    trimmed = [line for line in trimmed if line.strip() != r"\end{document}"]
    return trimmed


def apply_safe_ocr_fixes(lines: list[str]) -> list[str]:
    fixed: list[str] = []
    for line in lines:
        for old, new in SAFE_TEXT_REPLACEMENTS.items():
            line = line.replace(old, new)
        line = line.replace(r"\mathrm { { ; } }", "c")
        fixed.append(line)
    return fixed


def apply_safe_fixes_to_questions(questions: list[Question]) -> list[Question]:
    return [
        Question(
            chapter_key=question.chapter_key,
            chapter_display=question.chapter_display,
            number=question.number,
            lines=apply_safe_ocr_fixes(question.lines),
        )
        for question in questions
    ]


def chapter_question_counts(questions: list[Question]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for question in questions:
        counts[question.chapter_display] = counts.get(question.chapter_display, 0) + 1
    return counts


def parse_expected_counts(raw: str | None) -> dict[str, int]:
    if not raw:
        return {}
    counts: dict[str, int] = {}
    for index, item in enumerate(split_csv_arg(raw), start=1):
        if ":" in item or "=" in item:
            sep = ":" if ":" in item else "="
            key, value = item.split(sep, 1)
            counts[key.strip()] = int(value.strip())
        else:
            counts[str(index)] = int(item)
    return counts


def expected_count_for_chapter(chapter: str, position: int, expected: dict[str, int]) -> int | None:
    for key in (chapter, str(position)):
        if key in expected:
            return expected[key]
    match = re.search(r"第\s*([0-9一二三四五六七八九十百千零〇两]+)\s*章", chapter)
    if match:
        number = parse_cn_number(match.group(1))
        if number is not None and str(number) in expected:
            return expected[str(number)]
    return None


def review_questions(
    questions: list[Question],
    expected_total: int | None = None,
    expected_counts: dict[str, int] | None = None,
) -> list[ReviewFinding]:
    findings: list[ReviewFinding] = []
    expected_counts = expected_counts or {}

    if expected_total is not None and len(questions) != expected_total:
        findings.append(
            ReviewFinding(
                "error",
                "全书",
                f"题目总数 {len(questions)} 与期望 {expected_total} 不一致",
            )
        )

    counts = chapter_question_counts(questions)
    for position, (chapter, count) in enumerate(counts.items(), start=1):
        expected = expected_count_for_chapter(chapter, position, expected_counts)
        if expected is not None and count != expected:
            findings.append(
                ReviewFinding(
                    "error",
                    chapter,
                    f"章节题数 {count} 与期望 {expected} 不一致",
                )
            )

    seen_by_chapter: dict[str, set[str]] = {}
    for question in questions:
        scope = f"{question.chapter_display} 第 {question.number} 题"
        stripped_lines = trim_problem_lines(question.lines)
        text = "\n".join(stripped_lines)
        normalized = normalize_text(text)
        if not normalized:
            findings.append(ReviewFinding("error", scope, "题目内容为空"))
            continue
        if len(normalized) < 12:
            findings.append(
                ReviewFinding("warning", scope, "题目内容很短，可能漏识别", normalized[:80])
            )

        seen = seen_by_chapter.setdefault(question.chapter_display, set())
        if question.number in seen:
            findings.append(ReviewFinding("warning", scope, "同一章节内题号重复"))
        seen.add(question.number)

        for level, message, pattern in REVIEW_PATTERNS:
            match = pattern.search(text)
            if match:
                excerpt_start = max(match.start() - 40, 0)
                excerpt_end = min(match.end() + 40, len(text))
                excerpt = normalize_text(text[excerpt_start:excerpt_end])
                findings.append(ReviewFinding(level, scope, message, excerpt))
    return findings


def review_markdown_files(markdown_files: list[Path]) -> list[ReviewFinding]:
    findings: list[ReviewFinding] = []
    md_patterns = [
        ("warning", "疑似 OCR 替换字符", re.compile(r"�|□|■|\u001a")),
        ("warning", "常见 OCR 错字", re.compile(r"末知|做马分布|几匀分布")),
        ("warning", "损坏公式或题号片段", re.compile(r"8\.64|a1,\s*θ|L\s*\(a1|\?\s*\?")),
        ("warning", "疑似残留文档命令", re.compile(r"\\(?:begin|end)\{document\}|\\maketitle")),
    ]
    for path in markdown_files:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="replace")
        for level, message, pattern in md_patterns:
            for match in pattern.finditer(text):
                line_no = text.count("\n", 0, match.start()) + 1
                excerpt_start = max(match.start() - 40, 0)
                excerpt_end = min(match.end() + 40, len(text))
                excerpt = normalize_text(text[excerpt_start:excerpt_end])
                findings.append(
                    ReviewFinding(
                        level,
                        f"{path.name}:{line_no}",
                        f"Markdown 对照: {message}",
                        excerpt,
                    )
                )
                if sum(1 for item in findings if item.scope.startswith(path.name)) >= 80:
                    break
    return findings


def write_review_report(
    out_dir: Path,
    questions: list[Question],
    findings: list[ReviewFinding],
    section_issues: list[str],
    question_issues: list[str],
    markdown_files: list[Path] | None = None,
    mineru_issues: list[str] | None = None,
) -> Path:
    counts = chapter_question_counts(questions)
    markdown_files = markdown_files or []
    mineru_issues = mineru_issues or []
    report_path = out_dir / "exercise_workbook_review.md"
    lines = [
        "# 做题本自动审查报告",
        "",
        f"- 题目总数: {len(questions)}",
        f"- 章节数: {len(counts)}",
        "- 章节题数:",
    ]
    for chapter, count in counts.items():
        lines.append(f"  - {chapter}: {count}")
    if markdown_files:
        lines.extend(["", "## Markdown 对照文件"])
        for path in markdown_files:
            lines.append(f"- {path}")
    if mineru_issues:
        lines.extend(["", "## MinerU 提取提醒"])
        for issue in mineru_issues:
            lines.append(f"- {issue}")
    if section_issues or question_issues:
        lines.extend(["", "## 结构提醒"])
        for issue in [*section_issues, *question_issues]:
            lines.append(f"- {issue}")
    if findings:
        lines.extend(["", "## 规则命中"])
        for finding in findings:
            lines.append(f"- [{finding.level}] {finding.scope}: {finding.message}")
            if finding.excerpt:
                lines.append(f"  - `{finding.excerpt}`")
    else:
        lines.extend(["", "## 规则命中", "- 未发现内置规则可疑项。"])
    report_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return report_path


def build_compact_body(questions: list[Question]) -> str:
    body_parts: list[str] = []
    current_chapter: str | None = None

    for question in questions:
        if current_chapter != question.chapter_key:
            current_chapter = question.chapter_key
            body_parts.append(rf"\worksheetchapter{{{question.chapter_display}}}")
            body_parts.append("")
        body_parts.append(rf"\problemnumber{{{question.number}}}")
        body_parts.extend(trim_problem_lines(question.lines))
        body_parts.append("")
    return "\n".join(body_parts).rstrip() + "\n"


def build_spaced_body(questions: list[Question]) -> str:
    body_parts: list[str] = []
    current_chapter: str | None = None

    for index, question in enumerate(questions):
        if current_chapter != question.chapter_key:
            current_chapter = question.chapter_key
            body_parts.append(rf"\worksheetchapter{{{question.chapter_display}}}")
        body_parts.append(rf"\problemnumber{{{question.number}}}")
        body_parts.extend(trim_problem_lines(question.lines))
        body_parts.append("")
        body_parts.append(r"\problemend" if index < len(questions) - 1 else r"\problemlast")
        body_parts.append("")
    return "\n".join(body_parts).rstrip() + "\n"


def count_chapters(questions: list[Question]) -> int:
    seen: set[str] = set()
    ordered: list[str] = []
    for question in questions:
        if question.chapter_key in seen:
            continue
        seen.add(question.chapter_key)
        ordered.append(question.chapter_key)
    return len(ordered)


def run_latexmk(tex_file: Path, out_dir: Path, engine: str = "auto") -> str:
    env = os.environ.copy()
    env["XDG_CACHE_HOME"] = str(out_dir / ".cache")
    env["HOME"] = str(out_dir / ".cache-home")
    env["TMP"] = str(out_dir / ".cache")
    env["TEMP"] = str(out_dir / ".cache")
    (out_dir / ".cache").mkdir(parents=True, exist_ok=True)
    (out_dir / ".cache-home").mkdir(parents=True, exist_ok=True)

    engines = ["xelatex", "lualatex"] if engine == "auto" else [engine]
    logs: list[tuple[str, str]] = []
    for selected_engine in engines:
        cmd = [
            "latexmk",
            f"-{selected_engine}",
            "-interaction=nonstopmode",
            "-halt-on-error",
            tex_file.name,
        ]
        result = subprocess.run(
            cmd,
            cwd=out_dir,
            env=env,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        output = "\n".join(
            part.strip() for part in (result.stdout, result.stderr) if part.strip()
        )
        if result.returncode == 0:
            return selected_engine
        logs.append((selected_engine, output))

    engine_log = "\n\n".join(
        f"== {failed_engine} ==\n"
        + ("\n".join(output.splitlines()[-60:]) if output else "无可用编译日志。")
        for failed_engine, output in logs
    )
    raise RuntimeError(f"{tex_file.name} 编译失败，日志尾部如下：\n{engine_log}")


def clean_intermediate(out_dir: Path, stem: str) -> None:
    for suffix in (".aux", ".fdb_latexmk", ".fls", ".log", ".out", ".xdv", ".toc"):
        target = out_dir / f"{stem}{suffix}"
        if target.exists():
            target.unlink()
    for cache_name in (".cache", ".cache-home"):
        cache_dir = out_dir / cache_name
        if cache_dir.exists():
            shutil.rmtree(cache_dir, ignore_errors=True)


def parse_page_numbers(raw: str | None) -> list[int] | None:
    if not raw:
        return None
    pages: list[int] = []
    for item in raw.split(","):
        value = item.strip()
        if not value:
            continue
        if not value.isdigit():
            raise ValueError(f"宣传图页码必须是正整数: {value}")
        page = int(value)
        if page <= 0:
            raise ValueError(f"宣传图页码必须大于 0: {value}")
        pages.append(page)
    return pages or None


def choose_promo_body_pages(body_start: int, body_count: int, sample_count: int) -> list[int]:
    if body_count <= 0 or sample_count <= 0:
        return []
    if body_count <= sample_count:
        return [body_start + index for index in range(body_count)]

    if sample_count == 1:
        fractions = [0.5]
    elif sample_count == 2:
        fractions = [0.35, 0.85]
    elif sample_count == 4:
        fractions = [0.30, 0.45, 0.60, 0.98]
    else:
        fractions = [(index + 1) / (sample_count + 1) for index in range(sample_count)]

    selected: list[int] = []
    seen: set[int] = set()
    for fraction in fractions:
        offset = round((body_count - 1) * fraction)
        page = body_start + max(0, min(body_count - 1, offset))
        if page not in seen:
            selected.append(page)
            seen.add(page)

    cursor = body_start
    while len(selected) < sample_count and cursor < body_start + body_count:
        if cursor not in seen:
            selected.append(cursor)
            seen.add(cursor)
        cursor += 1
    return selected[:sample_count]


def render_promo_images(
    pdf_path: Path,
    out_dir: Path,
    include_cover: bool,
    include_toc: bool,
    problem_count: int,
    promo_count: int,
    dpi: int,
    promo_pages: list[int] | None = None,
) -> list[Path]:
    if promo_count <= 0:
        return []
    if dpi <= 0:
        raise ValueError("--promo-dpi 必须大于 0")

    pdftoppm_cmd = shutil.which("pdftoppm")
    if not pdftoppm_cmd:
        raise RuntimeError("缺少 pdftoppm，无法生成宣传图。请安装 Poppler 或使用 --skip-promo。")

    promo_dir = out_dir / "promo_images"
    promo_dir.mkdir(parents=True, exist_ok=True)
    for old_file in promo_dir.glob("宣传图_*.png"):
        old_file.unlink()
    for tmp_file in promo_dir.glob("promo_tmp_*.png"):
        tmp_file.unlink()

    if promo_pages:
        pages = promo_pages[:promo_count]
    else:
        pages = []
        if include_cover:
            pages.append(1)
        body_start = 1 + int(include_cover) + int(include_toc)
        pages.extend(
            choose_promo_body_pages(
                body_start,
                problem_count,
                max(0, promo_count - len(pages)),
            )
        )
        pages = pages[:promo_count]

    if not pages:
        return []

    rendered: list[Path] = []
    for index, page in enumerate(pages, start=1):
        prefix = promo_dir / f"promo_tmp_{index:02d}"
        for tmp_file in promo_dir.glob(f"{prefix.name}-*.png"):
            tmp_file.unlink()
        cmd = [
            pdftoppm_cmd,
            "-png",
            "-r",
            str(dpi),
            "-f",
            str(page),
            "-l",
            str(page),
            str(pdf_path),
            str(prefix),
        ]
        result = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            output = "\n".join(
                part.strip() for part in (result.stdout, result.stderr) if part.strip()
            )
            raise RuntimeError(f"第 {page} 页宣传图渲染失败：{output or '无可用日志'}")

        generated = sorted(promo_dir.glob(f"{prefix.name}-*.png"))
        if not generated:
            raise RuntimeError(f"第 {page} 页宣传图渲染完成但未找到输出文件")

        if page == 1 and include_cover:
            target_name = f"宣传图_{index:02d}_封面.png"
        else:
            target_name = f"宣传图_{index:02d}_一页一题_第{page}页.png"
        target = promo_dir / target_name
        if target.exists():
            target.unlink()
        generated[0].replace(target)
        rendered.append(target)
    return rendered


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="从 OCR/LaTeX 生成 A4 做题本 PDF")
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="一个或多个 PDF/OCR tex 文件，或包含这些文件的目录",
    )
    parser.add_argument(
        "--output-dir",
        help="输出目录。默认使用首个输入所在目录下的 exercise_book_output",
    )
    parser.add_argument(
        "--output-prefix",
        default="exercise_workbook",
        help="输出文件名前缀，默认 exercise_workbook",
    )
    parser.add_argument(
        "--ocr",
        action="store_true",
        help="输入含 PDF 时先调用 MinerU OCR，默认发现 PDF 且没有 tex 时自动启用",
    )
    parser.add_argument(
        "--ocr-output-dir",
        help="MinerU OCR 输出目录，默认使用输出目录下 mineru_ocr",
    )
    parser.add_argument(
        "--ocr-formats",
        default="latex,md",
        help="MinerU 输出格式，默认 latex,md；正式流程推荐保留两种并逐格式调用以兼容 CLI",
    )
    parser.add_argument(
        "--ocr-model",
        default="pipeline",
        help="MinerU 模型，默认 pipeline；正式流程推荐保持此值，遇到特定文档再单独试 vlm",
    )
    parser.add_argument(
        "--ocr-language",
        default="ch",
        help="MinerU 语言，默认 ch",
    )
    parser.add_argument(
        "--ocr-timeout",
        type=int,
        default=1800,
        help="MinerU 单文件超时秒数，默认 1800；正式流程推荐保持或按大书上调",
    )
    parser.add_argument(
        "--ocr-pages",
        help="MinerU 页码范围，例如 1-20；仅建议局部调试时使用，正式流程默认不限制页码",
    )
    parser.add_argument(
        "--book-title",
        help="页眉右上角书名。默认自动识别；识别失败时使用“做题本”",
    )
    parser.add_argument(
        "--brand",
        default=DEFAULT_BRAND,
        help=f"页眉左上角文案，默认 {DEFAULT_BRAND}",
    )
    parser.add_argument(
        "--cover-image",
        help="封面头像或配图路径，支持 png/jpg/jpeg/pdf；webp 等格式会尝试自动转为 png",
    )
    parser.add_argument(
        "--exercise-keywords",
        default=",".join(DEFAULT_EXERCISE_KEYWORDS),
        help="识别习题节的关键词，逗号分隔",
    )
    parser.add_argument(
        "--exclude-keywords",
        default=",".join(DEFAULT_EXCLUDE_KEYWORDS),
        help="排除节标题关键词，逗号分隔",
    )
    parser.add_argument(
        "--question-pattern",
        action="append",
        default=[],
        help="额外题号正则，可重复传入；正则需包含 num 命名组，可选 rest 命名组",
    )
    parser.add_argument(
        "--expected-count",
        type=int,
        help="期望题目总数；正式流程建议必填，且以各章最后一题题号求和为准",
    )
    parser.add_argument(
        "--expected-chapter-counts",
        help="期望每章题数，逗号分隔。可写 12,55,51 或 '第一章 习题一:12,第二章 习题二:55'；正式流程建议必填",
    )
    review_group = parser.add_mutually_exclusive_group()
    review_group.add_argument(
        "--strict-review",
        action="store_true",
        default=True,
        help="自动审查命中 error 时停止，不继续编译（默认开启）",
    )
    review_group.add_argument(
        "--no-strict-review",
        action="store_false",
        dest="strict_review",
        help="关闭严格审查，仅用于调试中间结果",
    )
    parser.add_argument(
        "--latex-engine",
        choices=LATEX_ENGINES,
        default="auto",
        help="编译引擎，默认 auto：先 xelatex，失败后 lualatex",
    )
    parser.add_argument(
        "--skip-compile",
        action="store_true",
        help="只生成 tex 和正文文件，不编译 PDF",
    )
    parser.add_argument(
        "--no-cover",
        action="store_true",
        help="不生成封面页",
    )
    parser.add_argument(
        "--no-toc",
        action="store_true",
        help="不生成目录页",
    )
    parser.add_argument(
        "--skip-promo",
        action="store_true",
        help="不生成宣传图；默认从留白版 PDF 输出封面加正文样张",
    )
    parser.add_argument(
        "--promo-count",
        type=int,
        default=DEFAULT_PROMO_COUNT,
        help=f"宣传图张数，默认 {DEFAULT_PROMO_COUNT}",
    )
    parser.add_argument(
        "--promo-dpi",
        type=int,
        default=DEFAULT_PROMO_DPI,
        help=f"宣传图渲染 DPI，默认 {DEFAULT_PROMO_DPI}",
    )
    parser.add_argument(
        "--promo-pages",
        help="手动指定宣传图 PDF 页码，逗号分隔；例如 1,81,121,151,261",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    inputs = normalize_input_paths(args.inputs)

    if args.output_dir:
        out_dir = Path(args.output_dir).expanduser().resolve()
    else:
        base = inputs[0].parent if inputs[0].is_file() else inputs[0]
        out_dir = base / "exercise_book_output"
    out_dir.mkdir(parents=True, exist_ok=True)

    pdf_files = discover_pdf_files(inputs)
    tex_files = discover_tex_files(inputs, required=False)
    markdown_files = discover_markdown_files(inputs)
    mineru_issues: list[str] = []
    should_ocr = bool(pdf_files) and (args.ocr or not tex_files)
    if should_ocr:
        ocr_out_dir = (
            Path(args.ocr_output_dir).expanduser().resolve()
            if args.ocr_output_dir
            else out_dir / "mineru_ocr"
        )
        formats = split_csv_arg(args.ocr_formats)
        print(f"正在调用 MinerU OCR：{len(pdf_files)} 个 PDF -> {ocr_out_dir}")
        mineru_issues = run_mineru_extract(
            pdf_files,
            ocr_out_dir,
            formats,
            args.ocr_model,
            args.ocr_language,
            args.ocr_timeout,
            args.ocr_pages,
        )
        tex_files = discover_tex_files([ocr_out_dir], required=False)
        markdown_files = [*markdown_files, *discover_markdown_files([ocr_out_dir])]
    if not tex_files:
        raise FileNotFoundError("没有找到任何 .tex 文件；PDF OCR 也没有生成 LaTeX")

    output_prefix = sanitize_filename_prefix(args.output_prefix)
    compact_tex_name = f"{output_prefix}_compact.tex"
    compact_body_name = f"{output_prefix}_compact_body.tex"
    spaced_tex_name = f"{output_prefix}_one_problem_per_page.tex"
    spaced_body_name = f"{output_prefix}_one_problem_per_page_body.tex"

    exercise_keywords = split_csv_arg(args.exercise_keywords)
    exclude_keywords = split_csv_arg(args.exclude_keywords)
    question_patterns = compile_question_patterns(args.question_pattern)

    sections, headings, section_issues = collect_exercise_sections(
        tex_files, out_dir, exercise_keywords, exclude_keywords, question_patterns
    )
    if not sections:
        raise RuntimeError("没有识别出任何习题节，请调整 --exercise-keywords 或检查 tex 结构")

    questions, question_issues = parse_questions(sections, question_patterns)
    if not questions:
        raise RuntimeError("识别到了习题节，但没有解析出任何题目，请补充 --question-pattern")
    questions = apply_safe_fixes_to_questions(questions)

    book_title = args.book_title or infer_book_title(headings, tex_files)
    include_cover = not args.no_cover
    include_toc = not args.no_toc
    chapter_count = count_chapters(questions)
    cover_image_rel = prepare_cover_image(args.cover_image, out_dir)
    compact_body = build_compact_body(questions)
    spaced_body = build_spaced_body(questions)
    compact_tex = build_compact_tex(
        book_title,
        args.brand,
        compact_body_name,
        len(questions),
        chapter_count,
        include_cover,
        include_toc,
        cover_image_rel,
    )
    spaced_tex = build_spaced_tex(
        book_title,
        args.brand,
        spaced_body_name,
        len(questions),
        chapter_count,
        include_cover,
        include_toc,
        cover_image_rel,
    )

    (out_dir / compact_body_name).write_text(compact_body, encoding="utf-8")
    (out_dir / compact_tex_name).write_text(compact_tex, encoding="utf-8")
    (out_dir / spaced_body_name).write_text(spaced_body, encoding="utf-8")
    (out_dir / spaced_tex_name).write_text(spaced_tex, encoding="utf-8")

    print("已写出：")
    print(out_dir / compact_tex_name)
    print(out_dir / compact_body_name)
    print(out_dir / spaced_tex_name)
    print(out_dir / spaced_body_name)
    print(f"识别书名：{book_title}")
    print(f"识别习题节数：{len(sections)}")
    print(f"解析题目总数：{len(questions)}")

    issues = [*section_issues, *question_issues]
    review_findings = [
        *review_questions(
        questions,
        expected_total=args.expected_count,
        expected_counts=parse_expected_counts(args.expected_chapter_counts),
        ),
        *review_markdown_files(markdown_files),
    ]
    report_path = write_review_report(
        out_dir,
        questions,
        review_findings,
        section_issues,
        question_issues,
        markdown_files,
        mineru_issues,
    )
    print(f"自动审查报告：{report_path}")
    if issues:
        print("结构提醒：")
        for issue in issues[:12]:
            print("-", issue)
    if review_findings:
        error_count = sum(1 for finding in review_findings if finding.level == "error")
        warning_count = sum(1 for finding in review_findings if finding.level != "error")
        print(f"自动审查命中：error={error_count}, warning={warning_count}")
        for finding in review_findings[:12]:
            print(f"- [{finding.level}] {finding.scope}: {finding.message}")
        if args.strict_review and error_count:
            raise RuntimeError(
                f"自动审查存在 {error_count} 个 error，已停止。详见 {report_path}"
            )

    if args.skip_compile:
        return

    generated_pdfs: list[Path] = []
    for tex_name in (compact_tex_name, spaced_tex_name):
        tex_path = out_dir / tex_name
        print(f"正在编译：{tex_path.name}")
        used_engine = run_latexmk(tex_path, out_dir, args.latex_engine)
        clean_intermediate(out_dir, tex_path.stem)
        pdf_path = tex_path.with_suffix(".pdf")
        generated_pdfs.append(pdf_path)
        print(f"编译完成：{pdf_path.name} ({used_engine})")

    chinese_outputs = [
        out_dir / chinese_pdf_name(book_title, "紧凑"),
        out_dir / chinese_pdf_name(book_title, "留白"),
    ]
    for source, target in zip(generated_pdfs, chinese_outputs):
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)

    print("已生成 PDF：")
    for pdf_path in chinese_outputs:
        print(pdf_path)

    if not args.skip_promo:
        promo_images = render_promo_images(
            chinese_outputs[1],
            out_dir,
            include_cover,
            include_toc,
            len(questions),
            args.promo_count,
            args.promo_dpi,
            parse_page_numbers(args.promo_pages),
        )
        if promo_images:
            print("已生成宣传图：")
            for image_path in promo_images:
                print(image_path)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"执行失败：{exc}", file=sys.stderr)
        sys.exit(1)
