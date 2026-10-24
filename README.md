# arxiv-translator

一个 [Claude Code](https://claude.com/claude-code) Skill：把 arXiv 论文自动翻译成中文 PDF，同时保留**英文原版**与**中文译版**两套可独立编译的 LaTeX 源码、Makefile 和 PDF。

- 翻译由对话模型自身完成，不调用外部翻译 API
- 严格保持数学公式、`\cite{}`、`\ref{}`、图片路径、代码本体不变
- 内置译后自检（正文 / 图表标题）、PDF 质量检查、文字溢出检查
- 支持断点续传，中断后从上次阶段继续
- 支持同步到 Zotero（MCP，可选，失败自动降级）

## 工作流程

```
确定论文 ID
  → 下载 arXiv 源码并定位主文件
  → 复制出英文 / 中文两套源码，只翻译中文目录
  → 译后自检（inspect_tex.py / inspect_captions.py）
  → 生成两份 Makefile，分别编译英文 PDF 与中文 PDF
  → PDF 质量检查 + 溢出检查
  → 同步到 Zotero（可选）
```

中文 PDF 使用 LuaLaTeX + Fandol 字体（TeX Live 自带）本地编译，避免依赖系统字体与远程编译服务。

## 目录结构

```
arxiv-translator/
├── SKILL.md                     # Skill 主文件（触发条件、五步流程、约束）
├── README.md
├── references/
│   └── compile-errors.md        # 编译常见错误及修复方法
└── scripts/
    ├── download.py              # 下载/解压 arXiv 源码，定位主 .tex 与标题
    ├── inspect_tex.py           # 扫描未翻译的英文正文
    ├── inspect_captions.py      # 扫描未翻译的图表标题
    ├── compile.py               # 提交 latex-on-http 远程编译（可选）
    ├── check_pdf_quality.py     # 检查未解析引用、乱码、缺失 .bbl
    ├── check_overflow.py        # 检查 overfull/underfull box
    └── cleanup.py               # 清理 .tmp_arxiv 临时目录
```

## 安装

把仓库放到 Claude Code 的 skills 目录：

```bash
git clone git@github.com:dongliangnie/arxiv-translator.git \
  ~/.claude/skills/arxiv-translator
```

Claude Code 启动时会自动发现 `~/.claude/skills/*/SKILL.md`。

### 依赖

| 依赖 | 用途 |
| --- | --- |
| Python 3.9+ | 运行 `scripts/*.py` |
| TeX Live（含 `texlive-lang-chinese`） | LuaLaTeX 编译、Fandol 字体 |
| LuaLaTeX / BibTeX | 中文与英文 PDF 编译 |
| Zotero MCP（可选） | 中文/英文 PDF 导入同一条目 |

Debian/Ubuntu 安装示例：

```bash
sudo apt-get install -y texlive-luatex texlive-lang-chinese texlive-xetex latexmk
```

## 使用

在 Claude Code 中直接提出请求即可触发，例如：

```
翻译论文 2502.14819
把 "Attention Is All You Need" 翻译成中文
我想读这篇 arXiv 论文的中文版：https://arxiv.org/abs/2405.05803
```

触发后 Skill 会自动完成：下载 → 建双份源码 → 翻译 → 自检 → 编译 → 质量检查 → 可选同步 Zotero。

### 输出

在 `OUTPUT_DIR`（默认当前目录）下：

```
<OUTPUT_DIR>/
├── <PAPER_ID>-en/                  # 英文源码 + Makefile
├── <PAPER_ID>-zh/                  # 中文源码 + Makefile
├── <PDF_NAME>-英文.pdf
└── <PDF_NAME>-中文.pdf
```

### 常用脚本

```bash
# 下载并定位主文件（输出 WORK_DIR / MAIN_TEX / PDF_NAME）
python3 scripts/download.py 2502.14819 /path/to/work

# 检查正文是否翻译完整
python3 scripts/inspect_tex.py scan /path/to/zh-dir main.tex body

# 检查图表标题是否翻译完整
python3 scripts/inspect_captions.py /path/to/zh-dir main.tex

# PDF 质量检查（未解析引用 / 乱码 / 缺失 .bbl）
python3 scripts/check_pdf_quality.py paper.pdf --strict

# 文字溢出检查
python3 scripts/check_overflow.py main.log 1
```

## 翻译约定

- **默认只翻译正文**，遇到 `\appendix` 停止；用户明确要求时才翻译附录
- **保持原样**：数学环境、LaTeX 命令、引用/标签、图片路径、URL、代码本体、`.bib`、人名、机构名、模型/数据集名
- **保留英文术语**：Transformer、Softmax、Token 等通用学术词
- **标题**：`\title{}` 改写为自然中文，不与英文并列；输出文件名沿用英文标题

## 故障排查

详见 [`references/compile-errors.md`](references/compile-errors.md)，常见问题：

- **中文显示为 `\ufffd`**：JFM 必须使用 `jfm-ujisv.lua`，并同时配置 `\setmainjfont`（宋体）与 `\setsansjfont`（黑体）；不要用 `luatexja-zhfonts.sty`
- **引用显示 `??` / `[?]`**：执行完整编译链 `lualatex → bibtex → lualatex → lualatex`
- **文字溢出**：拆句、调整表格列宽、添加 `\setlength{\emergencystretch}{3em}`
- **希腊字母被误报为乱码**：算法/数学环境中的 `µ`、`σ`、`π` 属误报，可忽略

## License

未指定。使用前请遵守 arXiv 论文原始许可证与 LaTeX 模板条款。
