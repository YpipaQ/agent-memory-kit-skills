#!/usr/bin/env bash
# 建交流测试目录（薄壳）：实现只有一份，在 agent-memory-kit 技能里。
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
WS=$(cd "$HERE/../.." && pwd)
for c in "${MEM_KIT_HOME:-}" "$HOME/.dsh/skills/agent-memory-kit" "{{KIT}}"; do
  [[ -n "$c" && -f "$c/scripts/new_exchange.sh" ]] || continue
  has_root=0
  for a in "$@"; do [[ "$a" == "--root" || "$a" == --root=* ]] && has_root=1; done
  if [[ $has_root -eq 1 ]]; then exec bash "$c/scripts/new_exchange.sh" "$@"; fi
  exec bash "$c/scripts/new_exchange.sh" --root "$WS" "$@"
done
echo "找不到 agent-memory-kit（设 MEM_KIT_HOME 指向技能目录，或确认 ~/.dsh/skills/agent-memory-kit 软链还在）" >&2
exit 3
