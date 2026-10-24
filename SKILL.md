---
name: arxiv-translator
description: 将 arXiv 论文自动翻译为中文 PDF，同时保留英文/中文 LaTeX 源码、分别生成两份 Makefile 和两份 PDF。触发词：翻译论文、翻译 arXiv、中文 PDF、我想读中文版、arXiv 翻译。触发后按本 skill 四步顺序直接执行，勿长篇规划。用户提供论文标题或 arXiv ID、说「翻译论文」「我想读中文版」等时立即使用。支持多篇论文处理。无需用户手动操作。
---

# arXiv 论文中文翻译

**目标：** 将指定论文的 LaTeX 源码译为中文，同时保留英文原版和中文译版源码，并分别生成可独立编译的 Makefile 与 PDF。

**流程：** 须严格按下文「第一步」至「第五步」顺序执行，不得擅自省略、合并或调换步骤。

**进度追踪：** 每次完成一个阶段后，必须更新进度状态文件 `$OUTPUT_DIR/.arxiv_translator_{PAPER_ID}_state.json`，记录当前完成的阶段和关键信息。中断后重新启动时，读取该文件判断从哪个阶段继续。

**交互：** 仅在论文 ID 无法确定、检索结果存在多个需用户择一才可向用户提问；其余情况一律无中断的执行得到最终翻译后的PDF。

**翻译：** 翻译全部由当前对话模型自身完成，严禁使用外部翻译工具以及下载已有的翻译版本。

---

## 第零步：检查进度状态（断点续传）

```bash
STATE_FILE="$OUTPUT_DIR/.arxiv_translator_{PAPER_ID}_state.json"

if [ -f "$STATE_FILE" ]; then
    # 读取进度状态
    CURRENT_STAGE=$(python3 -c "import json; print(json.load(open('$STATE_FILE')).get('stage', 'init'))")
    echo "检测到已有进度，继续执行。当前阶段: $CURRENT_STAGE"
else
    CURRENT_STAGE="init"
    echo "新任务，从头开始"
fi
```

**阶段定义：**
- `init`: 未开始
- `step1_done`: 第一步完成（已确定论文ID）
- `step2_done`: 第二步完成（已下载源码）
- `step3_body_done`: 第三步完成（仅正文已翻译，附录未翻）
- `step3_done`: 第三步完成（全文已翻译）
- `step4_done`: 第四步完成（已编译PDF）
- `step5_done`: 第五步完成（已同步Zotero）

**"继续翻译附录"处理：**
当用户说"继续翻译附录"时：
1. 读取状态文件获取当前进度
2. 若处于 `step3_body_done` 阶段，直接进入附录翻译流程
3. 若已完成 `step3_done`，说明全文已翻过，直接告知用户
4. 附录翻译完成后更新状态为 `step3_done`

根据 `$CURRENT_STAGE` 跳转到对应阶段继续执行。

---

## 第一步：确定论文 ID

- arXiv URL/ID → 直接提取 ID
- 论文标题 → 搜索 arXiv / 网页查找 ID；找不到时给出候选让用户确认

**完成后更新状态：**
```bash
python3 -c "import json; json.dump({'stage': 'step1_done', 'paper_id': '$PAPER_ID'}, open('$STATE_FILE', 'w'))"
```

---

## 第二步：获取源码并确定翻译范围

```bash
python3 {SKILL_DIR}/scripts/download.py "{PAPER_ID}" "$OUTPUT_DIR/.tmp_arxiv/{PAPER_ID}"
```

`download.py` 一步完成：下载源码 → 解压 → 递归查找 `.tex` → 定位主文件 → 提取标题。

`OUTPUT_DIR` 为用户指定的保存路径，未指定则为当前目录（即唤醒 Codex 的工作目录）。

无源码（仅 PDF）则告知用户跳过。

脚本向 stdout 输出三行，格式如下：
```
WORK_DIR=<源码目录绝对路径>
MAIN_TEX=<主文件相对路径>
PDF_NAME=<论文标题>
```

**完成后更新状态：**
```bash
python3 -c "import json; d=json.load(open('$STATE_FILE')); d.update({'stage': 'step2_done', 'work_dir': '$WORK_DIR', 'main_tex': '$MAIN_TEX', 'pdf_name': '$PDF_NAME'}); json.dump(d, open('$STATE_FILE', 'w'))"
```

---

## 第三步：建立双份源码并翻译

**必须保留英文原版，不得直接修改英文源码。** 下载完成后，在 `OUTPUT_DIR` 下建立两个独立源码目录：

- `<PAPER_ID>-en/`：保留下载得到的原始英文源码，原样保存；
- `<PAPER_ID>-zh/`：复制英文目录的全部内容，只在此目录中修改 `.tex` 进行翻译。

两个目录都必须包含完整的 `.tex`、`.bib`、图片、样式文件及其他依赖。`WORK_DIR` 指英文目录，`ZH_WORK_DIR` 指中文目录，`MAIN_TEX` 在两个目录中保持相同的相对路径。

由当前**对话模型**只在中文目录的 `.tex` 文件上进行翻译修改，按以下规则翻译：

- **翻译范围：** 默认只翻正文，不翻附录，但附录中的内容需要得到保留，若同一文件中出现 `\appendix`，默认只翻该命令之前的内容。用户明确要求"翻译全文"时才翻附录。
- **必须翻译：** 正文叙述、摘要、图表标题、列表项、脚注中的描述文本，以及代码块中的注释。
- **保留不翻：** 数学环境、LaTeX 命令、`\cite{}`/`\ref{}`/`\label{}`、图片路径、URL、代码本体、`.bib`、人名、机构名、模型名、数据集名。
- **专有名词：** Transformer、Softmax、Token 等通用学术术语保留英文，不要生硬硬译。
- **标题要求：** `\title{}` 须改为自然中文题名，不保留英文原题或中英并列；输出 PDF 文件名仍使用第二步的 `PDF_NAME`。
- **多篇处理：** 多篇论文可以分别处理；只有在用户**明确要求**并行委派时，才开启多个 subagent，否则直接顺序完成。
- **英文原版：** 英文目录中的 `.tex`、`.bib`、图片、样式和其他源码文件不得修改。

译后必须做自检：

```bash
python3 {SKILL_DIR}/scripts/inspect_tex.py scan "$ZH_WORK_DIR" "$MAIN_TEX" body
```

若用户明确要求"翻译全文"，则改为：

```bash
python3 {SKILL_DIR}/scripts/inspect_tex.py scan "$ZH_WORK_DIR" "$MAIN_TEX" full
```

脚本会输出 `SUSPECT_COUNT=<数字>` 以及若干 `SUSPECT=<文件>:<行号>:<片段>`。
- 只要 `SUSPECT_COUNT` 非 0，就必须逐条回到对应位置进行翻译；
- 只有 `SUSPECT_COUNT=0`，或剩余项明确属于"保留不翻"范围时，才可继续。

**此外，必须检查图/表标题翻译是否完整：**

```bash
python3 {SKILL_DIR}/scripts/inspect_captions.py "$ZH_WORK_DIR" "$MAIN_TEX"
```

脚本会扫描 `\caption{}`、`\captionof`、`\subfloat[]` 中的文本，若包含无 CJK 字符的英文标题则输出 `SUSPECT_COUNT` > 0。必须修正至 `SUSPECT_COUNT=0` 方可进入下一步。

**完成后更新状态（仅翻译正文时标记为 step3_body_done）：**
```bash
python3 -c "import json; d=json.load(open('$STATE_FILE')); d.update({'stage': 'step3_body_done', 'zh_work_dir': '$ZH_WORK_DIR'}); json.dump(d, open('$STATE_FILE', 'w'))"
```

---

## 第三步附：翻译附录（"继续翻译附录"时执行）

当用户说"继续翻译附录"时，检查状态文件：
- 若处于 `step3_body_done`，继续翻译附录
- 若已完成 `step3_done`，告知用户"全文已翻译完毕"

**附录翻译规则：**
- 仅翻译 `\appendix` 命令之后的内容
- 数学公式、算法、代码块内的文字仍需翻译
- 图/表标题、脚注中的描述文本需要翻译
- `\cite{}`、`\ref{}`、人名、机构名等保留不翻

**附录翻译完成后更新状态：**
```bash
python3 -c "import json; d=json.load(open('$STATE_FILE')); d.update({'stage': 'step3_done'}); json.dump(d, open('$STATE_FILE', 'w'))"
```

---

## 第四步：分别生成 Makefile、编译与清理

必须在英文目录和中文目录中各生成一个 `Makefile`。两个 Makefile 必须能在各自目录中独立编译对应主文件，不得引用另一个目录的源码；至少包含默认 `all` 目标和只删除本目录构建产物的 `clean` 目标。

英文 Makefile 使用普通英文 LaTeX 编译链；中文 Makefile 使用 LuaLaTeX/CJK 编译链，或调用 `compile.py` 的等价本地编译流程。Makefile 中使用相对路径或可覆盖变量，确保源码目录移动后仍可用。

必须生成并保留英文 PDF 和中文 PDF，PDF 放在对应源码目录的同级目录下：

- 中文 PDF：`$ZH_WORK_DIR/../$PDF_NAME-中文.pdf`
- 英文 PDF：`$WORK_DIR/../$PDF_NAME-英文.pdf`

**【关键】中文 PDF 必须使用 Fandol 字体本地编译：**

```bash
# 在中文 tex 文件 preamble 中添加 Fandol 字体配置（如果尚未添加）
# 检查是否已有 luatexja 配置，如果没有则添加
if ! grep -q "luatexja" "$ZH_WORK_DIR/$MAIN_TEX"; then
    # 在 \documentclass 之后、\begin{document} 之前插入字体配置
    sed -i '/\\documentclass/a\\usepackage{fontspec}\n\\usepackage{luatexja}\n\\usepackage{luatexja-fontspec}\n\\setmainjfont{FandolSong-Regular}[JFM={jfm-ujisv.lua},BoldFont=FandolSong-Bold]\n\\setsansjfont{FandolHei-Regular}[JFM={jfm-ujisv.lua},BoldFont=FandolHei-Bold}' "$ZH_WORK_DIR/$MAIN_TEX"
fi
```

**【关键】必须先运行 bibtex 再多次编译，确保引用解析：**

```bash
cd "$ZH_WORK_DIR"
lualatex --interaction=nonstopmode "$MAIN_TEX"
bibtex "$MAIN_TEX" || true
lualatex --interaction=nonstopmode "$MAIN_TEX"
lualatex --interaction=nonstopmode "$MAIN_TEX"
cd "$WORK_DIR"
lualatex --interaction=nonstopmode "$MAIN_TEX"
bibtex "$MAIN_TEX" || true
lualatex --interaction=nonstopmode "$MAIN_TEX"
lualatex --interaction=nonstopmode "$MAIN_TEX"
```

编译成功后，**必须** 分别执行 PDF 质量检查（使用 `--strict` 模式）：

```bash
python3 {SKILL_DIR}/scripts/check_pdf_quality.py "$WORK_DIR/../$PDF_NAME-英文.pdf" --strict
python3 {SKILL_DIR}/scripts/check_pdf_quality.py "$ZH_WORK_DIR/../$PDF_NAME-中文.pdf" --strict
```

**严格检查内容：**
- **未解析引用/引文（`??`、`[?]`、`(?)`）**：说明未运行 `bibtex`（或 `biber`）或 `.bbl` 缺失，需运行完整编译链（lualatex → bibtex → lualatex → lualatex）后再验证
- **LaTeX 日志警告**：从 `.log` 文件中检测 `Citation ... undefined`、`Reference ... undefined`、`Rerun to get ... right` 等警告
- **乱码文字（Unicode 替换字符 `\ufffd` 或控制字符）**：说明编译栈或字体有问题，需修复
- **.bbl 文件缺失**：如果有 `.bib` 但无 `.bbl`，说明 bibtex 未成功运行

脚本返回非 0 则必须修复问题后重新编译，直到 `check_pdf_quality.py` 返回 0。

**【关键】必须检查并修复文字溢出问题（使用 strict mode）：**

```bash
python3 {SKILL_DIR}/scripts/check_overflow.py "$ZH_WORK_DIR/acl_latex.log" 1
```

**严格检查内容：**
- **Overfull hbox（文字溢出）**：任何 > 0pt 的溢出在 strict 模式下都是错误
- **Overfull vbox（垂直溢出）**：内容超出容器高度
- **Undefined citations/references**：从 LaTeX 日志中检测引用失效
- **Underfull hbox（badness > 3000）**：高 badness 值可能导致排版问题

**若报告任何溢出或引用问题，必须修复：**

1. **Overfull hbox (> 0pt)：**
   - 在对应位置的 `.tex` 文件中，将长句拆分为多句
   - 在 preamble 添加 `\setlength{\emergencystretch}{3em}` 或更大的值（如 `5em`）
   - 对特定段落使用 `\begin{sloppy}` 切换断行策略
   - 图表题注过长时用 `\multicolumn` 或手动断行
   - 减少表格列数或调整表格宽度比例

2. **Undefined citation/reference：**
   - 确保 `.bib` 文件存在且格式正确
   - 确保 `\bibliography{custom}` 指向正确文件
   - 运行完整编译链：`lualatex → bibtex → lualatex → lualatex`

修复后重新编译并再次检查，直到所有检查通过。

编译成功后**不要删除**英文或中文 LaTeX 源码目录（`WORK_DIR`、`ZH_WORK_DIR` 及其内容必须保留在 `OUTPUT_DIR` 下），包括两个目录中的 `Makefile`。

如需清理，只删除两个源码目录中的编译中间文件（如 `.aux`、`.log` 等），不要移除源码目录、`Makefile`、`*.tex`、`*.bib`、图片或样式文件。

多篇论文时，所有论文都完成 PDF 编译并保存后再进行中间文件清理。

**完成后更新状态：**
```bash
python3 -c "import json; d=json.load(open('$STATE_FILE')); d.update({'stage': 'step4_done', 'en_pdf': '$WORK_DIR/../$PDF_NAME-英文.pdf', 'zh_pdf': '$ZH_WORK_DIR/../$PDF_NAME-中文.pdf'}); json.dump(d, open('$STATE_FILE', 'w'))"
```

---

## 第五步：同步到 Zotero

英文 PDF 与中文 PDF 编译成功并通过 `check_pdf_quality.py` 与 `check_overflow.py` 校验后，**必须**将两份 PDF 合并导入到 Zotero 的**同一个 item** 中，方便对照阅读。

**前置工具：** 已通过 `npx -y zotero-mcp` 在全局启用 zotero-mcp（详见 `~/.claude/settings.json` 的 `mcpServers.zotero`），MCP 工具命名以 `mcp__zotero__` 开头。

### 5.1 检测 Windows 用户路径

由于 `powershell.exe` 在 bash 环境中可能无法正常执行，改用以下稳健方法检测 Windows 用户目录：

```bash
# 方法1：尝试从 WSL 当前用户名推断
CURRENT_USER="$USER"
WIN_USER_HOME="/mnt/c/Users/$CURRENT_USER"

# 方法2：列出 /mnt/c/Users/ 查找有效用户目录
if [ ! -d "$WIN_USER_HOME" ] || [ ! -w "$WIN_USER_HOME" ]; then
    for dir in /mnt/c/Users/*/; do
        username=$(basename "$dir")
        # 跳过系统目录
        if [ "$username" != "All Users" ] && [ "$username" != "Default" ] && [ "$username" != "Default User" ] && [ "$username" != "Public" ] && [ "$username" != "desktop.ini" ]; then
            if [ -d "$dir/Downloads" ] && [ -w "$dir" ]; then
                WIN_USER_HOME="$dir"
                break
            fi
        fi
    done
fi

WIN_DOWNLOADS="$WIN_USER_HOME/Downloads"
WIN_ZOTERO_STORAGE="$WIN_USER_HOME/Zotero/storage"

echo "Windows user home: $WIN_USER_HOME"
echo "Downloads: $WIN_DOWNLOADS"
```

### 5.2 复制 PDF 到 Windows 路径

```bash
EN_PDF="$WORK_DIR/../$PDF_NAME-英文.pdf"
ZH_PDF="$ZH_WORK_DIR/../$PDF_NAME-中文.pdf"

# 生成不包含中文的文件名（避免路径编码问题）
EN_TMP_NAME="${PAPER_ID}-en.pdf"
ZH_TMP_NAME="${PAPER_ID}-zh.pdf"

mkdir -p "$WIN_DOWNLOADS"
cp -f "$EN_PDF" "$WIN_DOWNLOADS/$EN_TMP_NAME"
cp -f "$ZH_PDF" "$WIN_DOWNLOADS/$ZH_TMP_NAME"
echo "PDF 已复制到: $WIN_DOWNLOADS"
```

### 5.3 尝试 Zotero MCP 同步

```bash
# 检查 MCP 是否可用
MCP_AVAILABLE=false
if mcp__zotero__search_library --q "test" --limit 1 2>/dev/null; then
    MCP_AVAILABLE=true
fi

if [ "$MCP_AVAILABLE" = true ]; then
    # 按 DOI 搜索是否已存在 item
    SEARCH_RESULT=$(mcp__zotero__search_library --q "10.48550/arXiv.$PAPER_ID" --limit 1)
    # 解析结果判断是否存在...
    # 若存在则复用，若不存在则创建...
    # （完整 MCP 操作逻辑保持不变）
else
    echo "Zotero MCP 不可用，尝试降级方案..."
fi
```

### 5.4 降级方案：直接复制到 Zotero Storage

当 MCP 不可用或同步失败时，采用降级方案：

```bash
# 方案A：复制到 Zotero Storage 目录
if [ -d "$WIN_ZOTERO_STORAGE" ] && [ -w "$WIN_ZOTERO_STORAGE" ]; then
    # 创建以论文 ID 命名的子目录
    ZOTERO_TARGET="$WIN_ZOTERO_STORAGE/$PAPER_ID"
    mkdir -p "$ZOTERO_TARGET"

    # 复制文件（使用 ASCII 文件名）
    cp -f "$EN_PDF" "$ZOTERO_TARGET/$EN_TMP_NAME"
    cp -f "$ZH_PDF" "$ZOTERO_TARGET/$ZH_TMP_NAME"

    echo "已复制到 Zotero Storage: $ZOTERO_TARGET"
    echo "请在 Zotero 客户端中刷新库，或重新启动 Zotero 以扫描新文件"
else
    # 方案B：保留在 Downloads，用户手动导入
    echo "Zotero Storage 不可写，PDF 保留在 Downloads 目录"
    echo "请手动在 Zotero 中通过'添加附件'→'从文件添加'导入："
    echo "  - $WIN_DOWNLOADS/$EN_TMP_NAME"
    echo "  - $WIN_DOWNLOADS/$ZH_TMP_NAME"
fi
```

**关键改进点：**
1. 不再依赖 `powershell.exe`，改用目录遍历检测有效用户
2. 文件名使用论文 ID 而非中文标题，避免编码问题
3. MCP 不可用时自动降级到直接复制到 Zotero Storage
4. 所有路径操作使用绝对路径，避免 cd 相关问题

**约束：**
- **必须只创建一个 item**；多篇论文时为每篇各创建一个。
- 任何 Zotero 步骤失败（连接异常、API 错误、用户拒绝授权等）都**不得回滚已生成的 PDF**，只允许跳过 Zotero 同步并在最终结果中说明"Zotero 同步失败：<原因>"。
- 不要在 Zotero item 的 `title` 中使用中文（避免 Zotero Web API 解析错误），如需展示中文标题应写入 `extra` 字段或留空。

**完成后更新状态：**
```bash
python3 -c "import json; d=json.load(open('$STATE_FILE')); d.update({'stage': 'step5_done', 'zotero_item_key': '$ITEM_KEY'}); json.dump(d, open('$STATE_FILE', 'w'))"
```

---

## 完成后

完成后简要告知用户结果即可，无需列出详细路径。

清理状态文件（可选）：
```bash
rm -f "$STATE_FILE"
```

---

## 常见问题记录

### 1. 切记：先翻译，再编译

编译前如果未翻译，用户会给出"你根本没有翻译"的反馈。
**规则：** 必须在 inspect_tex.py scan/check_captions 通过后，确认所有正文已翻译为中文，再进入编译步骤。

---

### 2. CJK 字体配置（LuaLaTeX 本地编译）

`compile.py` 远程编译服务可能不可用，需本地编译。在 Linux（WSL）环境下，LuaTeX-ja 的中文字体配置要点：

- **使用 Fandol 字体**（TeXLive `texlive-lang-chinese` 自带），不依赖系统字体：
  ```latex
  \usepackage{fontspec}
  \usepackage{luatexja}
  \usepackage{luatexja-fontspec}
  \setmainjfont{FandolSong-Regular}[JFM={jfm-ujisv.lua},BoldFont=FandolSong-Bold]
  \setsansjfont{FandolHei-Regular}[JFM={jfm-ujisv.lua},BoldFont=FandolHei-Bold]
  ```
- **关键：JFM 必须用 `jfm-ujisv.lua`**（而非默认 `jfm-ujis.lua`），否则简化字（非 JIS X 0208 字符）会显示为 `\ufffd`（替换字符）。
- **不要用 `luatexja-zhfonts.sty`**：它会加载 HaranoAji 字体，缺少部分简化汉字形，导致粗体/标题中的 CJK 显示为 `\ufffd`。
- **`\setmainjfont` 用于正文**（Song/宋体），**`\setsansjfont` 用于粗体/标题**（Hei/黑体），两者都必须配置。

---

### 3. check_pdf_quality.py 误报

希腊字母（`µ`、`σ`、`π`、`φ` 等）在算法伪代码（algorithm2e 环境）中出现时，会被 `check_pdf_quality.py` 检测为"乱码字节"。

- **原因：** 检测脚本的正则 `[\x80-\xbf][\x00-\x7f]{2,}` 匹配了 UTF-8 多字节编码的希腊字母中的字节。
- **判断标准：** 若所有"乱码"均出现在**算法/代码/数学**环境中（如 `Lπ ← ...`、`µℓ`、`σℓ`），且 PDF 打开后希腊字母渲染正常，则为**可安全忽略的误报**，无需修复。
- **真正需要修复的乱码：** 正文、标题、摘要中出现的 `\ufffd`（白色菱形问号）。

---

### 4. compile.py 自动 CJK 补入的局限

`compile.py` 会在检测到中文后自动补入 CJK 支持，但补入的字体配置（`Noto Serif CJK SC`）在某些环境中可能因字体缺失而失败（替换字符 `\ufffd`）。在远程编译服务器（latex.ytotech.com）上 `Noto Serif CJK SC` 可用，但在本地 Linux/WSL 环境中建议手动改为 Fandol 字体。

---

### 5. 引用失效（??）的解决方法

如果 PDF 中出现 `??` 或 `[?]` 未解析引用，必须确保编译流程正确：
1. 确保 `.bib` 文件存在且格式正确
2. 确保 `\bibliography{custom}` 或类似命令指向正确的 bib 文件
3. 运行完整编译链：`lualatex → bibtex → lualatex → lualatex`
4. 检查 bibtex 是否成功运行（无错误输出）

---

### 6. 文字溢出（Overflow）的解决方法

中文翻译后常见文字溢出问题，按以下优先级修复：
1. **高优先级（溢出 > 3pt）：**
   - 将长句拆分为短句
   - 减少表格列数或调整列宽比例
   - 图表题注换行
2. **中优先级：**
   - 在 preamble 添加 `\setlength{\emergencystretch}{3em}`
   - 对特定段落使用 `\begin{sloppy}` 或 `\fussy`
3. **低优先级（溢出 ≤ 3pt）：**
   - 可接受，不强制修复

---

## 参考文件
- `references/compile-errors.md`：编译常见错误及修复方法
