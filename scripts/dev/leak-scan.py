#!/usr/bin/env python3
"""Leak-scan gate: block private identifiers from entering commits.

Modes:
  leak-scan.py            scan staged files (pre-commit gate)
  leak-scan.py --all      scan the entire working tree (repo-wide audit)
  leak-scan.py <paths..>  scan specific files

Exit codes: 0 = clean, 1 = hits found, 2 = usage/internal error.

The identifier list is assembled from fragments so the scanner file itself
does not contain the verbatim tokens it hunts (a redaction list can itself
be a leak). The scanner skips itself by path.
"""

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SELF_PATH = Path(__file__).resolve()

# Fragments joined at runtime so verbatim tokens never sit in this file.
_J = lambda *parts: "".join(parts)

# (label, regex, allow_regex_or_None)
RULES = [
    ("home-path", re.compile(_J("/Users/", "neo", "force"), re.I), None),
    ("username", re.compile(_J("neo", "force"), re.I), None),
    ("owner-name", re.compile(r"\b" + _J("rob", "in") + r"\b", re.I), None),
    ("biz-1", re.compile(_J("rev", "ane"), re.I), None),
    ("infra-1", re.compile(_J("hetz", "ner"), re.I), None),
    ("infra-2", re.compile(r"\b" + _J("lu", "cy") + r"\b", re.I), None),
    ("engram-local", re.compile(_J("Business/", "eng", "ram"), re.I), None),
    ("biz-2", re.compile(_J("auswander", "ung"), re.I), None),
    ("biz-3", re.compile(_J("thrive", "vibes"), re.I), None),
    # primeline allowed ONLY as the org slug / author attribution.
    ("author-brand", re.compile(_J("prime", "line"), re.I),
     re.compile(_J("prime", "line") + r"(-ai|\.cc)|PrimeLine(Direkt)?\b", re.I)),
]

BINARY_EXT = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".woff", ".woff2",
              ".ttf", ".pdf", ".zip", ".gz", ".mp4", ".mov"}


def staged_files() -> list[Path]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    return [REPO_ROOT / p for p in out if p.strip()]


def tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout.splitlines()
    return [REPO_ROOT / p for p in out if p.strip()]


def scan_file(path: Path) -> list[str]:
    if path.resolve() == SELF_PATH or path.suffix.lower() in BINARY_EXT:
        return []
    try:
        text = path.read_text(errors="ignore")
    except (OSError, IsADirectoryError):
        return []
    hits = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for label, pattern, allow in RULES:
            m = pattern.search(line)
            if not m:
                continue
            if allow is not None and allow.search(line):
                continue
            hits.append(f"{path.relative_to(REPO_ROOT)}:{lineno}: [{label}] {line.strip()[:120]}")
    return hits


def main() -> int:
    args = sys.argv[1:]
    if args == ["--all"]:
        files = tracked_files()
    elif args:
        files = [Path(a).resolve() for a in args]
    else:
        files = staged_files()

    all_hits = []
    for f in files:
        if f.exists() and f.is_file():
            all_hits.extend(scan_file(f))

    if all_hits:
        print("LEAK-SCAN: BLOCKED - private identifiers found:", file=sys.stderr)
        for h in all_hits:
            print(f"  {h}", file=sys.stderr)
        return 1
    print(f"LEAK-SCAN: clean ({len(files)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
