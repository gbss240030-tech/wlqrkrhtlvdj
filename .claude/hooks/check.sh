#!/usr/bin/env bash
# 파일 수정 후 ruff check와 pytest를 돌린다. 실패하면 exit 2로 결과를 Claude에게 돌려준다.
cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}" || exit 0
export UV_NO_PROGRESS=1
out=$( { uv run --quiet ruff check && uv run --quiet pytest -q -p no:cacheprovider; } 2>&1 )
status=$?
if [ $status -ne 0 ]; then
  printf '%s\n' "$out" | tail -n 60 >&2
  exit 2
fi
exit 0
