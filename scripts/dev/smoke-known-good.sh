#!/usr/bin/env bash
# Known-good component smoke test (clean-room oracle proof).
# Runs security-tier-check.py with deterministic inputs and asserts exit codes.
set -uo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../.."
HOOK=hooks/scripts/security-tier-check.py
FAIL=0

run_case() {
  local desc="$1" cmd="$2" expected="$3"
  printf '{"tool_input":{"command":%s}}' "$(python3 -c 'import json,sys;print(json.dumps(sys.argv[1]))' "$cmd")" \
    | python3 "$HOOK" >/dev/null 2>&1
  local actual=$?
  if [ "$actual" -eq "$expected" ]; then
    echo "PASS: $desc (exit $actual)"
  else
    echo "FAIL: $desc (expected exit $expected, got $actual)"
    FAIL=1
  fi
}

# Import smoke: shared lib loads cleanly.
python3 -c "import sys; sys.path.insert(0, 'hooks/scripts/lib'); import common; print('PASS: lib/common.py imports, PLUGIN_ROOT=' + str(common.PLUGIN_ROOT))" || FAIL=1

# Benign command must be allowed (exit 0).
run_case "benign command allowed" "ls -la" 0

# Catastrophic command must be blocked (exit 2).
run_case "catastrophic command blocked" "rm -rf / --no-preserve-root" 2

if [ "$FAIL" -eq 0 ]; then
  echo "SMOKE: ALL GREEN"
else
  echo "SMOKE: FAILURES PRESENT"
  exit 1
fi
