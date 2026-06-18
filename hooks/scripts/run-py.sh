#!/usr/bin/env bash
# Shared Python launcher for evolving-lite hooks (cross-platform).
#
# WHY THIS EXISTS
# ----------------
# hooks.json used to invoke `python3 -X utf8 ...` directly. Claude Code runs
# shell-form hook commands through Git Bash on Windows, but it does NOT
# guarantee that the token `python3` resolves: the python.org installer ships
# `python.exe` / `py.exe`, not `python3.exe`, so a bare `python3` silently
# no-ops on many Windows boxes. This shim is the SINGLE place hooks resolve an
# interpreter, using the same order as scripts/doctor.py and setup.sh
# (python3 -> python -> py). The verifier (doctor) and the runtime (hooks) now
# agree on how Python is found.
#
# CONTRACT
#   bash run-py.sh <script.py> [args...]
#   - forwards every argument unchanged to the interpreter
#   - `exec` preserves stdin (hooks receive their JSON payload on stdin) and
#     the child's exit code
#   - injects `-X utf8` so the Windows cp1252 console codec never breaks
#     UTF-8 source reads (parity with the old inline invocation)
#   - fail-open: if no interpreter is found, exit 0 so a missing Python never
#     blocks a tool call
#
# OVERRIDE: set EVOLVING_PYTHON to an explicit interpreter path to skip
# discovery (Claude Code expands ${EVOLVING_PYTHON} in hook commands too).
set -euo pipefail

PY="${EVOLVING_PYTHON:-}"
if [ -z "$PY" ]; then
  for cand in python3 python py; do
    if command -v "$cand" >/dev/null 2>&1; then PY="$cand"; break; fi
  done
fi

if [ -z "$PY" ]; then
  exit 0  # fail-open: no interpreter -> never block the tool
fi

exec "$PY" -X utf8 "$@"
