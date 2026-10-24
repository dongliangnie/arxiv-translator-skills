#!/usr/bin/env python3
"""
Check compiled PDF's .log file for overfull/underfull warnings (text overflow/overlap).

Usage:
    python check_overflow.py <log_path> [strict_mode]

strict_mode: 0 = allow small overflow (<=3pt), 1 = any overflow is error (default: 0)

Returns exit code 0 if no issues, 1 if issues found.
"""
import re
import sys


_OVERFULL_HBOX_RE = re.compile(
    r"Overfull \\hbox \((\d+(?:\.\d+)?)pt too wide\)"
    r"(?:\s*has occurred while \w+ is output)?"
    r"(?:\s*at lines?\s+(\d+)(?:--(\d+))?)?"
    r"(.*?)(?=\n(?:Underfull|Overfull|$))",
    re.DOTALL | re.MULTILINE
)

_UNDERFULL_HBOX_RE = re.compile(
    r"Underfull \\hbox \(badness (\d+)(?: \d+)?\)(?: at lines?\s+(\d+)(?:--(\d+))?)?"
    r"(.*?)(?=\n(?:Underfull|Overfull|$))",
    re.DOTALL | re.MULTILINE
)

_OVERFULL_VBOX_RE = re.compile(
    r"Overfull \\vbox \((\d+(?:\.\d+)?)pt too tall\)"
    r"(?:\s*at page \d+)?"
    r"(?:, input line (\d+))?",
    re.DOTALL
)

_BADSTRETCH_RE = re.compile(
    r"Badness \((\d+)\) in \\vsplit",
    re.DOTALL
)

_CITATION_WARN_RE = re.compile(
    r"LaTeX Warning: Citation `([^']+)' on page (\d+) undefined",
    re.MULTILINE
)

_REF_WARN_RE = re.compile(
    r"LaTeX Warning: Reference `([^']+)' on page (\d+) undefined",
    re.MULTILINE
)

_UNDERFUL_HBOX_THRESHOLD = 3000
_OVERFUL_THRESHOLD_PT = 0.5


def parse_log(log_path, strict_mode=False):
    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except OSError:
        return None

    overfulls = []
    for m in _OVERFULL_HBOX_RE.finditer(content):
        overflow_pt = float(m.group(1))
        start_line = m.group(2)
        end_line = m.group(3)
        snippet = m.group(4).strip()
        overfulls.append({
            "type": "overfull_hbox",
            "overflow_pt": overflow_pt,
            "start_line": int(start_line) if start_line else None,
            "end_line": int(end_line) if end_line else None,
            "snippet": snippet[:200],
        })

    underfulls = []
    for m in _UNDERFULL_HBOX_RE.finditer(content):
        badness = int(m.group(1))
        if badness < _UNDERFUL_HBOX_THRESHOLD:
            continue
        start_line = m.group(2)
        end_line = m.group(3)
        snippet = m.group(4).strip()
        underfulls.append({
            "type": "underfull_hbox",
            "badness": badness,
            "start_line": int(start_line) if start_line else None,
            "end_line": int(end_line) if end_line else None,
            "snippet": snippet[:200],
        })

    overfull_vboxs = []
    for m in _OVERFULL_VBOX_RE.finditer(content):
        overflow_pt = float(m.group(1))
        input_line = m.group(2)
        overfull_vboxs.append({
            "type": "overfull_vbox",
            "overflow_pt": overflow_pt,
            "input_line": int(input_line) if input_line else None,
        })

    citation_warns = []
    for m in _CITATION_WARN_RE.finditer(content):
        citation = m.group(1)
        page = m.group(2)
        citation_warns.append({
            "type": "citation_undefined",
            "citation": citation,
            "page": page,
        })

    ref_warns = []
    for m in _REF_WARN_RE.finditer(content):
        ref = m.group(1)
        page = m.group(2)
        ref_warns.append({
            "type": "reference_undefined",
            "reference": ref,
            "page": page,
        })

    return {
        "overfulls": overfulls,
        "underfulls": underfulls,
        "overfull_vboxs": overfull_vboxs,
        "citation_warns": citation_warns,
        "ref_warns": ref_warns,
        "strict_mode": strict_mode,
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python check_overflow.py <log_path> [strict_mode]", file=sys.stderr)
        sys.exit(1)

    log_path = sys.argv[1]
    strict_mode = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    result = parse_log(log_path, strict_mode)

    if result is None:
        print(f"ERROR: could not read log file: {log_path}", file=sys.stderr)
        sys.exit(1)

    overfulls = result["overfulls"]
    underfulls = result["underfulls"]
    overfull_vboxs = result["overfull_vboxs"]
    citation_warns = result["citation_warns"]
    ref_warns = result["ref_warns"]

    critical_issues = []

    for item in overfulls:
        overflow_pt = item["overflow_pt"]
        if strict_mode:
            if overflow_pt > 0:
                critical_issues.append(item)
        else:
            if overflow_pt > 3.0:
                critical_issues.append(item)

    if citation_warns:
        critical_issues.extend(citation_warns)

    if ref_warns:
        critical_issues.extend(ref_warns)

    if overfull_vboxs:
        for item in overfull_vboxs:
            if item["overflow_pt"] > 3.0:
                critical_issues.append(item)

    if not critical_issues and not underfulls:
        print("Overflow check: PASSED (no critical issues found)")
        sys.exit(0)

    total = len(critical_issues) + len(underfulls)
    print(f"Overflow check: FAILED ({total} issue(s) found)")
    print()

    if citation_warns:
        print(f"--- Undefined Citations ({len(citation_warns)}) ---")
        for item in citation_warns:
            print(f"  [page {item['page']}] Citation '{item['citation']}' undefined")
        print()

    if ref_warns:
        print(f"--- Undefined References ({len(ref_warns)}) ---")
        for item in ref_warns:
            print(f"  [page {item['page']}] Reference '{item['reference']}' undefined")
        print()

    if overfulls:
        severe_overfulls = [x for x in overfulls if (strict_mode and x["overflow_pt"] > 0) or x["overflow_pt"] > 3.0]
        if severe_overfulls:
            print(f"--- Overfull Hbox / Text Overflow ({len(severe_overfulls)}) ---")
            for item in severe_overfulls:
                lines_str = ""
                if item["start_line"]:
                    lines_str = f" (lines {item['start_line']}"
                    if item["end_line"] and item["end_line"] != item["start_line"]:
                        lines_str += f"-{item['end_line']}"
                    lines_str += ")"
                print(f"  [{item['overflow_pt']:.1f}pt overflow]{lines_str}")
                if item["snippet"]:
                    print(f"    Content: ...{item['snippet'][:150]}...")
            print()

    if overfull_vboxs:
        severe_vboxs = [x for x in overfull_vboxs if x["overflow_pt"] > 3.0]
        if severe_vboxs:
            print(f"--- Overfull Vbox / Vertical Overflow ({len(severe_vboxs)}) ---")
            for item in severe_vboxs:
                line_str = f" (line {item['input_line']})" if item["input_line"] else ""
                print(f"  [{item['overflow_pt']:.1f}pt too tall]{line_str}")
            print()

    if underfulls:
        print(f"--- Underfull Hbox ({len(underfulls)}, badness > {_UNDERFUL_HBOX_THRESHOLD}) ---")
        for item in underfulls[:10]:
            lines_str = ""
            if item["start_line"]:
                lines_str = f" (lines {item['start_line']}"
                if item["end_line"] and item["end_line"] != item["start_line"]:
                    lines_str += f"-{item['end_line']}"
                lines_str += ")"
            print(f"  [badness {item['badness']}]{lines_str}")
        if len(underfulls) > 10:
            print(f"  ... and {len(underfulls) - 10} more (omitted)")
        print("  (Underfull hbox with high badness may cause text overlap/spacing issues)")
        print()

    if critical_issues:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
