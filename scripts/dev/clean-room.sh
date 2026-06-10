#!/usr/bin/env bash
# Clean-room harness: run a command against the COMMITTED tree of this repo
# inside an isolated Docker container with NO host mounts.
#
# Isolation properties (the correctness oracle for the self-* port):
#   - Only `git archive HEAD` travels into the container (committed tree only;
#     untracked/dirty files and host paths never enter).
#   - No bind mounts: the host filesystem (including any private repos) is
#     unreachable by construction.
#   - HOME and XDG_* point at scratch dirs inside the container.
#
# Usage:
#   scripts/dev/clean-room.sh                          # run default smoke test
#   scripts/dev/clean-room.sh bash scripts/dev/smoke-known-good.sh
#   scripts/dev/clean-room.sh python3 -m pytest tests/
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
IMAGE="${CLEANROOM_IMAGE:-python:3.12-slim}"

if ! docker info >/dev/null 2>&1; then
  echo "clean-room: docker daemon not reachable" >&2
  exit 3
fi

CMD=("$@")
if [ ${#CMD[@]} -eq 0 ]; then
  CMD=(bash scripts/dev/smoke-known-good.sh)
fi

# Stage the committed tree as a tarball on stdin; unpack and run inside.
git -C "$REPO_ROOT" archive HEAD | docker run --rm -i \
  --network none \
  -e HOME=/scratch/home \
  -e XDG_CONFIG_HOME=/scratch/xdg-config \
  -e XDG_DATA_HOME=/scratch/xdg-data \
  -e XDG_CACHE_HOME=/scratch/xdg-cache \
  -e CLAUDE_PLUGIN_ROOT=/cleanroom \
  "$IMAGE" \
  bash -c '
    set -euo pipefail
    mkdir -p /cleanroom /scratch/home /scratch/xdg-config /scratch/xdg-data /scratch/xdg-cache
    tar -x -C /cleanroom
    cd /cleanroom
    # Isolation self-check: the host FS must not be visible.
    if [ -d /Users ]; then echo "ISOLATION BREACH: /Users visible" >&2; exit 4; fi
    exec "$@"
  ' -- "${CMD[@]}"
