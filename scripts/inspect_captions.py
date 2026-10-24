#!/usr/bin/env python3
"""
Check that all figure/table captions (non-appendix) have been translated.

Scans all .tex files in the input chain before \appendix, extracts
\caption{}, \captionof[]{}, and \subfloat[] text, and flags any that
contain no CJK characters (i.e., likely untranslated English).

Usage:
  python inspect_captions.py <work_dir> <main_tex>

Output:
  SUSPECT_COUNT=<n>
  CAPTION=<file>:<lineno>:<snippet>
"""
import os
import re
import sys
from typing import List, Optional, Tuple

INPUT_RE = re.compile(r"\\(input|include|subfile)\{([^}]+)\}")
CAPTION_RE = re.compile(r"\\(?:caption(?:\{[^}]*\})?|captionof)\{[^}]*\}\{([^}]*)\}")
SUBFLOAT_RE = re.compile(r"\\subfloat\[([^\]]*)\]")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
APPENDIX_RE = re.compile(r"\\appendix\b")


def _norm_path(work_dir: str, raw: str) -> Optional[str]:
    raw = raw.strip()
    if not raw:
        return None
    candidates = [raw]
    if not raw.lower().endswith(".tex"):
        candidates.append(raw + ".tex")
    for c in candidates:
        p = os.path.normpath(os.path.join(work_dir, c))
        if os.path.exists(p) and os.path.isfile(p):
            return p
    return None


def _walk_body_includes(work_dir: str, main_tex: str) -> List[str]:
    work_dir = os.path.abspath(work_dir)
    main_abs = main_tex if os.path.isabs(main_tex) else os.path.join(work_dir, main_tex)
    main_abs = os.path.abspath(main_abs)

    results: List[str] = []
    seen: set[str] = set()
    stop = False
    queue = [main_abs]

    while queue and not stop:
        cur = os.path.abspath(queue.pop(0))
        if cur in seen or not os.path.exists(cur):
            continue
        seen.add(cur)

        try:
            with open(cur, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except OSError:
            continue

        if APPENDIX_RE.search(text):
            body_end = APPENDIX_RE.search(text).start()
            body_text = text[:body_end]
        else:
            body_text = text

        results.append(cur)

        for m in INPUT_RE.finditer(body_text):
            inc = _norm_path(os.path.dirname(cur), m.group(2))
            if inc and inc.startswith(work_dir + os.sep) and inc not in seen:
                queue.append(inc)

    return results


def scan(work_dir: str, main_tex: str) -> List[Tuple[str, int, str]]:
    suspects: List[Tuple[str, int, str]] = []
    for path in _walk_body_includes(work_dir, main_tex):
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except OSError:
            continue

        lines = text.split("\n")
        for lineno, line in enumerate(lines, 1):
            for m in CAPTION_RE.finditer(line):
                content = m.group(1)
                if content and not CJK_RE.search(content):
                    suspects.append((path, lineno, content[:160]))
            for m in SUBFLOAT_RE.finditer(line):
                content = m.group(1)
                if content and not CJK_RE.search(content):
                    suspects.append((path, lineno, content[:160]))

    return suspects


def main():
    if len(sys.argv) != 3:
        print("Usage: python inspect_captions.py <work_dir> <main_tex>", file=sys.stderr)
        sys.exit(1)

    work_dir, main_tex = sys.argv[1], sys.argv[2]
    suspects = scan(work_dir, main_tex)

    print(f"SUSPECT_COUNT={len(suspects)}")
    for path, lineno, snippet in suspects:
        rel = os.path.relpath(path, os.path.abspath(work_dir))
        print(f"CAPTION={rel}:{lineno}:{snippet}")

    sys.exit(1 if suspects else 0)


if __name__ == "__main__":
    main()
