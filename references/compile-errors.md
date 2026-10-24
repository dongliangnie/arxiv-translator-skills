# 编译错误速查

## 常见错误与修复

**字体未找到** `Font "XXX" not found`
→ 请求的 CJK 字体在远程服务器上不存在。改用已确认可用的字体：`Noto Serif CJK SC`（已在 latex.ytotech.com 验证）。

**宏包冲突**（`fontenc` 或 `inputenc`）
→ 注释掉 `\usepackage[T1]{fontenc}` 和 `\usepackage[utf8]{inputenc}`——XeLaTeX / LuaLaTeX 的 Unicode 编译栈原生支持 UTF-8，通常不需要这两个包。

**宏重复定义** `LaTeX Error: Command \xxx already defined`
→ 常见于为中文支持引入 `luatexja` 后，与论文源码里的 `\newcommand\xxx...` 冲突。优先把源码中的该行从 `\newcommand` 改为 `\renewcommand`（保留论文作者期望的宏定义）。

**编译“成功”但引用/交叉引用仍是问号**（PDF 里出现 `??` 或 `[?]`）
→ 这通常意味着编译过程里发生了 LaTeX 错误，但在 `nonstopmode` 下仍生成了 PDF，导致 `latexmk` 没能完成多次编译而解析引用/交叉引用。
→ 解决思路：开启 `-halt-on-error`（让错误直接失败并返回日志）并修复首个报错后重试。

**宏包缺失** `File 'xxx.sty' not found`
→ 该包未安装在远程服务器上。可在 `https://latex.ytotech.com/packages` 查询可用包列表。若缺失，尝试注释掉该包或替换为等价的可用包。

**中文溢出 / Overfull \hbox**
→ 翻译后中文往往比英文更长，容易出现文字溢出。修复优先级：
1. **轻度溢出（< 5pt）**：在 preamble 添加或增大 `\setlength{\emergencystretch}{3em}`（已默认配置）
2. **中度溢出（5-15pt）**：
   - 使用 `\sloppy` 切换至宽松断行模式
   - 或在特定段落使用 `{\raggedright ... \par}` 左对齐
3. **重度溢出（> 15pt）**：必须手动修复，在 `.tex` 中拆分长句或改写
4. **图表/表格内溢出**：题注过长时用 `\elligent`、 `\newline` 断行；表格内容用 `\makecell` 或 `\begin{tabular}{p{width}}` 限制列宽

**Underfull hbox / 内容不足**
→ badness < 1000 可忽略；badness > 1000 表示排版过松。常见于使用 `\raggedright` 时。修复：适当缩短句子或调整 `\raggedright` 范围。

**行号定位**：
→ LaTeX log 中的 "Overfull \hbox at line N" 指该行**结束位置**在源码的第 N 行，而非问题根源在该行。从该行向前追溯找长句。

**参考文献问题（bibtex/biber）**
→ 确认 `.bib` 文件已存在于工作目录并被正确引用；若论文自带 `.bbl` 而没有 `.bib`，优先复用 `.bbl`。如需 biber，在请求中设置 `options.bibliography.command`。

**远端编译超时 / 变慢**
→ 检查工作目录里是否混入了历史产物（尤其是无关的 PDF、`.aux`、`.log`、旧输出文件）。这些文件会被一并上传，显著拖慢远端编译，甚至导致超时。

## 读取错误日志

编译失败时，服务端返回含完整日志的 JSON。找到以 `!` 开头的行定位致命错误：

```
! LaTeX Error: ...
! Undefined control sequence ...
! Missing $ inserted ...
```

优先修复第一个错误——后续错误通常是连锁反应。
