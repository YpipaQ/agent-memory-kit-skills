#!/usr/bin/env bash
# 收工同步（薄壳）：实现只有一份，在 agent-memory-kit-skills 技能里 —— **别在此处改逻辑**。
# 技能目录怎么找：环境变量 MEM_KIT_HOME → 本文件里的 {{KIT}} 占位符（bootstrap 铺开时替换）。
# 自动补 --root <工作区>：本文件在 <工作区>/scratch/memory-tooling/ 下，上两级就是工作区根，
# 所以**任意 cwd 都能跑**。这里不写死任何系统路径。
set -euo pipefail
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
WS=$(cd "$HERE/../.." && pwd)
for c in "${MEM_KIT_HOME:-}" "{{KIT}}"; do
  [[ -n "$c" && "$c" != *"{{"* && -f "$c/scripts/closeout.sh" ]] || continue
  has_root=0
  for a in "$@"; do [[ "$a" == "--root" || "$a" == --root=* ]] && has_root=1; done
  if [[ $has_root -eq 1 ]]; then exec bash "$c/scripts/closeout.sh" "$@"; fi
  exec bash "$c/scripts/closeout.sh" --root "$WS" "$@"
done
echo "找不到 agent-memory-kit-skills：设 MEM_KIT_HOME=<技能目录> 重试，或重新跑一次 bootstrap.sh（它会把技能目录填进本文件）" >&2
exit 3
