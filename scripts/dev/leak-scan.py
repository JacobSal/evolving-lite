#!/usr/bin/env python3
"""Leak-scan gate: block private identifiers from entering commits.

Modes:
  leak-scan.py            scan STAGED INDEX BLOBS (pre-commit gate)
  leak-scan.py --all      scan the entire tracked tree (repo-wide audit)
  leak-scan.py <paths..>  scan specific working-tree files

Exit codes: 0 = clean, 1 = hits found, 2 = usage/internal error.

The identifier list is assembled from fragments so the scanner file itself
does not contain the verbatim joined tokens it hunts (a redaction list can
itself be a leak; the joined strings never appear in this source). The
scanner skips itself by path.
"""

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SELF_REL = "scripts/dev/leak-scan.py"

# Fragments joined at runtime so verbatim tokens never sit in this file.
_J = lambda *parts: "".join(parts)

# (label, regex, allow_regex_or_None)
RULES = [
    ("home-path", re.compile(_J("/Users/", "neo", "force"), re.I), None),
    ("username", re.compile(_J("neo", "force"), re.I), None),
    ("owner-name", re.compile(r"\b" + _J("rob", "in") + r"\b", re.I),
     re.compile(r"round-" + _J("rob", "in"), re.I)),
    ("biz-1", re.compile(_J("rev", "ane"), re.I), None),
    ("infra-1", re.compile(_J("hetz", "ner"), re.I), None),
    ("infra-2", re.compile(r"\b" + _J("lu", "cy") + r"\b", re.I), None),
    ("engram-local", re.compile(_J("Business/", "eng", "ram"), re.I), None),
    ("biz-2", re.compile(_J("auswander", "ung"), re.I), None),
    ("biz-3", re.compile(_J("thrive", "vibes"), re.I), None),
    # primeline allowed ONLY as org slug / domain / author display name
    # (case-sensitive display forms); any other use is flagged.
    ("author-brand", re.compile(_J("prime", "line"), re.I),
     re.compile(_J("prime", "line") + r"(-ai|\.cc)|"
                + _J("Prime", "Line") + r" (AI|Ecosystem|Skills)")),
]

BINARY_EXT = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2",
              ".ttf", ".pdf", ".zip", ".gz", ".mp4", ".mov"}


def _git(args: list[str]) -> str:
    return subprocess.run(["git", *args], cwd=REPO_ROOT,
                          capture_output=True, text=True, check=True).stdout


def staged_paths() -> list[str]:
    out = _git(["diff", "--cached", "--name-only", "--diff-filter=ACMRT"])
    return [p for p in out.splitlines() if p.strip()]


def tracked_paths() -> list[str]:
    return [p for p in _git(["ls-files"]).splitlines() if p.strip()]


def read_index_blob(rel_path: str) -> str | None:
    """Read the STAGED content (index blob), not the working tree -
    a partially staged file must be judged by what will actually commit."""
    res = subprocess.run(["git", "show", f":{rel_path}"], cwd=REPO_ROOT,
                         capture_output=True)
    if res.returncode != 0:
        return None
    return res.stdout.decode(errors="ignore")


def scan_text(rel_path: str, text: str) -> list[str]:
    hits = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for label, pattern, allow in RULES:
            if not pattern.search(line):
                continue
            if allow is not None and allow.search(line):
                continue
            hits.append(f"{rel_path}:{lineno}: [{label}] {line.strip()[:120]}")
    return hits


def _scannable(rel_path: str) -> bool:
    return rel_path != SELF_REL and Path(rel_path).suffix.lower() not in BINARY_EXT


def main() -> int:
    args = sys.argv[1:]
    all_hits = []

    if args == ["--all"]:
        for p in tracked_paths():
            if not _scannable(p):
                continue
            blob = read_index_blob(p)
            if blob is not None:
                all_hits.extend(scan_text(p, blob))
        n = len(tracked_paths())
    elif args:
        for a in args:
            fp = Path(a).resolve()
            rel = str(fp.relative_to(REPO_ROOT)) if fp.is_relative_to(REPO_ROOT) else str(fp)
            if not _scannable(rel) or not fp.is_file():
                continue
            all_hits.extend(scan_text(rel, fp.read_text(errors="ignore", encoding="utf-8")))
        n = len(args)
    else:
        paths = staged_paths()
        for p in paths:
            if not _scannable(p):
                continue
            blob = read_index_blob(p)
            if blob is not None:
                all_hits.extend(scan_text(p, blob))
        n = len(paths)

    if all_hits:
        print("LEAK-SCAN: BLOCKED - private identifiers found:", file=sys.stderr)
        for h in all_hits:
            print(f"  {h}", file=sys.stderr)
        return 1
    print(f"LEAK-SCAN: clean ({n} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
