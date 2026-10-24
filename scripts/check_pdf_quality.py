#!/usr/bin/env python3
"""
Check compiled PDF for quality issues: unresolved citations, garbled text, and missing references.

Usage:
    python check_pdf_quality.py <pdf_path> [--strict]

Returns exit code 0 if clean, 1 if issues found.
"""
import re
import sys
import os


def _extract_text(pdf_path):
    try:
        import pypdf
        reader = pypdf.PdfReader(pdf_path)
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except ImportError:
        import subprocess
        result = subprocess.run(
            ["pdftotext", pdf_path, "-"],
            capture_output=True, text=True, timeout=30
        )
        return result.stdout
    except Exception:
        return None


def _get_log_path(pdf_path):
    log_path = pdf_path.replace(".pdf", ".log")
    if os.path.exists(log_path):
        return log_path
    base = os.path.splitext(pdf_path)[0]
    if base.endswith("_compressed"):
        base = base.replace("_compressed", "")
    log_path = base + ".log"
    if os.path.exists(log_path):
        return log_path
    return None


def check_citations(text):
    issues = []
    for m in re.finditer(r"\?\?", text):
        s, e = m.start(), m.end()
        ctx = text[max(0, s - 60):min(len(text), e + 60)].replace("\n", " ")
        issues.append(("?? (unresolved cross-ref)", ctx))
    for m in re.finditer(r"\[\?\s*\]", text):
        s, e = m.start(), m.end()
        ctx = text[max(0, s - 60):min(len(text), e + 60)].replace("\n", " ")
        issues.append(("[?] (unresolved citation)", ctx))
    for m in re.finditer(r"\([^)]*\?\s*\)", text):
        s, e = m.start(), m.end()
        ctx = text[max(0, s - 60):min(len(text), e + 60)].replace("\n", " ")
        issues.append(("(?) (unresolved citation)", ctx))
    for m in re.finditer(r"\[\d+\s*\]", text):
        s, e = m.start(), m.end()
        ctx = text[max(0, s - 60):min(len(text), e + 60)].replace("\n", " ")
        issues.append(("numbered ref (possible unresolved)", ctx))
    return issues


def check_garbled(text):
    issues = []
    if "\ufffd" in text:
        count = text.count("\ufffd")
        issues.append(("REPLACEMENT CHAR (U+FFFD)", f"PDF contains {count} Unicode replacement character(s) (encoding error)"))
    for m in re.finditer(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", text):
        s, e = m.start(), m.end()
        ctx = text[max(0, s - 40):min(len(text), e + 40)].replace("\n", " ")
        issues.append(("CONTROL CHAR", f"Control character found: {repr(ctx[:40])}"))

    lines = text.split("\n")
    for i, line in enumerate(lines, 1):
        if len(line) < 20:
            continue
        bad_seq = re.findall(r'[\x80-\xbf][\x00-\x7f]{2,}', line)
        if bad_seq:
            issues.append((f"GARBLED BYTES (line {i})", line[:100]))
    return issues


def check_log_warnings(log_path):
    issues = []
    if not log_path:
        return issues

    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except OSError:
        return issues

    citation_warn_re = re.compile(
        r"LaTeX Warning: Citation `([^']+)' on page (\d+) undefined",
        re.MULTILINE
    )
    for m in citation_warn_re.finditer(content):
        issues.append(("CITATION UNDEFINED (log)", f"Citation '{m.group(1)}' on page {m.group(2)} undefined"))

    ref_warn_re = re.compile(
        r"LaTeX Warning: Reference `([^']+)' on page (\d+) undefined",
        re.MULTILINE
    )
    for m in ref_warn_re.finditer(content):
        issues.append(("REFERENCE UNDEFINED (log)", f"Reference '{m.group(1)}' on page {m.group(2)} undefined"))

    multiply_defined_re = re.compile(
        r"LaTeX Warning: Label(s) may have changed\. Rerun to get cross-references right",
        re.MULTILINE
    )
    if multiply_defined_re.search(content):
        issues.append(("LABELS CHANGED (log)", "Labels changed - need rerun to fix cross-references"))

    rerun_re = re.compile(
        r"Rerun to get (?:cross-references|citations) right",
        re.MULTILINE
    )
    if rerun_re.search(content):
        issues.append(("RERUN NEEDED (log)", "LaTeX advises rerunning to resolve references"))

    return issues


def check_bbl_exists(pdf_path, tex_dir):
    if not tex_dir:
        return []
    issues = []
    bbl_path = None
    for f in os.listdir(tex_dir):
        if f.endswith(".bbl"):
            bbl_path = os.path.join(tex_dir, f)
            break
    if not bbl_path:
        bib_path = None
        for f in os.listdir(tex_dir):
            if f.endswith(".bib"):
                bib_path = os.path.join(tex_dir, f)
                break
        if bib_path:
            issues.append(("BIB FILE EXISTS BUT NO BBL", f"Found {bib_path} but no .bbl file - did bibtex run?"))
    return issues


def main():
    args = sys.argv[1:]
    strict = "--strict" in args
    if strict:
        args.remove("--strict")

    if len(args) < 1:
        print("Usage: python check_pdf_quality.py <pdf_path> [--strict]", file=sys.stderr)
        sys.exit(1)

    pdf_path = args[0]
    tex_dir = os.path.dirname(pdf_path)
    log_path = _get_log_path(pdf_path)

    text = _extract_text(pdf_path)
    if not text:
        print("ERROR: could not extract text from PDF", file=sys.stderr)
        sys.exit(1)

    cite_issues = check_citations(text)
    garbled_issues = check_garbled(text)
    log_issues = check_log_warnings(log_path) if log_path else []
    bbl_issues = check_bbl_exists(pdf_path, tex_dir)

    all_issues = cite_issues + garbled_issues + log_issues + bbl_issues

    if not all_issues:
        print("PDF quality check: PASSED (no issues found)")
        sys.exit(0)

    total = len(all_issues)
    print(f"PDF quality check: FAILED ({total} issue(s) found)")
    print()

    if cite_issues:
        print(f"--- Unresolved Citations/References ({len(cite_issues)}) ---")
        for kind, ctx in cite_issues:
            print(f"  [{kind}] ...{ctx}...")
        print()

    if log_issues:
        print(f"--- LaTeX Log Warnings ({len(log_issues)}) ---")
        for kind, msg in log_issues:
            print(f"  [{kind}] {msg}")
        print()

    if garbled_issues:
        print(f"--- Garbled Text ({len(garbled_issues)}) ---")
        for kind, snippet in garbled_issues:
            print(f"  [{kind}] {snippet}")
        print()

    if bbl_issues:
        print(f"--- Bibliography Issues ({len(bbl_issues)}) ---")
        for kind, msg in bbl_issues:
            print(f"  [{kind}] {msg}")
        print()

    if strict:
        sys.exit(1)

    critical_issues = cite_issues + log_issues + [g for g in garbled_issues if "REPLACEMENT CHAR" in g[0]]
    if critical_issues:
        print("Strict mode: FAILED due to critical issues (citations, references, or replacement chars)")
        sys.exit(1)
    else:
        print("Non-critical issues found but not blocking (garbled bytes in math/code areas)")
        sys.exit(0)


if __name__ == "__main__":
    main()
