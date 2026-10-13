#!/usr/bin/env bash
# 收工同步（六步一键）—— 改完任何东西就跑它，别分步挑着跑。
#
# 为什么有它（用户口径 2026-10-13）：踩过的坑不是"不知道要同步"，而是"查过、改了，
# 文件没当场跟上"。分步跑就会漏步 ⇒ 合成一条命令，任一步不过就停在这里。
#
#   1/6 台账重建      memory_query --rebuild（台账跟上磁盘）
#   2/6 活窗口刷新    memory_query --refresh（刷新各区 README 活窗口）
#   3/6 失效硬值扫描  check_stale_values（严区未声明即失败 → 当场处理，或写进基线并给理由）
#   4/6 状态表        state_snapshot（生成 + --check 新鲜度）—— **必须在体检前**，否则体检会报
#                     "STATE.md 比数据源旧"（那是它自己的产物，不是问题）
#   5/6 体检          memory_doctor（最后跑，其结论才可信）
#   6/6 热区形态      hot_cap_check（**只报告不判失败**：够格就提示"可扩 +10 行"，见 AGENTS.md 扩容口径）
#
# 用法：
#   bash <工作区>/scratch/memory-tooling/closeout.sh     # 薄壳；自动补 --root，任意 cwd 可跑
#   bash scripts/closeout.sh --root <工作区>              # 直接调真身
# 环境：PY 覆盖解释器（默认 python3）；MEM_KIT_ROOT 也可指定工作区根
# 退出码：0 = 前五步全绿（第六步只报告）；1 = 某步未通过；2 = 用法/根目录错
set -uo pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
KIT=$(cd "$HERE/.." && pwd)

ROOT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) ROOT="${2:?--root 需要路径}"; shift 2 ;;
    --root=*) ROOT="${1#--root=}"; shift ;;
    -h|--help) sed -n '2,20p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "!! 未知参数：$1" >&2; exit 2 ;;
  esac
done
PY="${PY:-python3}"

# 工作区根：--root → MEM_KIT_ROOT → 从当前目录向上找"工作区特征"（所以任意 cwd 都能跑）
[[ -n "$ROOT" ]] || ROOT="${MEM_KIT_ROOT:-}"
if [[ -z "$ROOT" ]]; then
  d=$PWD
  while :; do
    if [[ -f "$d/.memory-kit.toml" || ( -f "$d/AGENTS.md" && -d "$d/memory" ) ]]; then ROOT=$d; break; fi
    [[ "$d" == "/" ]] && break
    d=$(dirname "$d")
  done
fi
if [[ -z "$ROOT" || ! -d "$ROOT" ]]; then
  echo "!! 找不到工作区根：用 --root <工作区> 或设 MEM_KIT_ROOT 重试（当前目录 $PWD 不是工作区）" >&2
  exit 2
fi
ROOT=$(cd "$ROOT" && pwd)

step() { printf '\n== %s ==\n' "$1"; }
die()  { printf '\n❌ 收工未通过（%s）：先处理，再重跑本脚本\n' "$1" >&2; exit 1; }

printf '收工同步 @ %s —— 技能 %s\n' "$ROOT" "$KIT"

step "1/6 台账重建"
"$PY" "$KIT/scripts/memory_query.py" --root "$ROOT" --rebuild || die "台账重建"

step "2/6 活窗口刷新"
"$PY" "$KIT/scripts/memory_query.py" --root "$ROOT" --refresh || die "活窗口刷新"

step "3/6 失效硬值扫描（改名/搬家/退役 → 当场处理，或写进基线并给理由）"
if [[ -f "$KIT/scripts/check_stale_values.py" ]]; then
  "$PY" "$KIT/scripts/check_stale_values.py" --root "$ROOT" || die "失效硬值扫描"
else
  die "失效硬值扫描（技能里没有 scripts/check_stale_values.py —— v2.0.2 新增件，还没落地）"
fi

step "4/6 状态表（生成 + 新鲜度）"
"$PY" "$KIT/scripts/state_snapshot.py" --root "$ROOT" || die "STATE.md 生成"
"$PY" "$KIT/scripts/state_snapshot.py" --root "$ROOT" --check || die "STATE.md 新鲜度"

step "5/6 体检（最后跑）"
"$PY" "$KIT/scripts/memory_doctor.py" --root "$ROOT" || die "体检"

step "6/6 热区形态（只报告）"
if [[ -f "$KIT/scripts/hot_cap_check.py" ]]; then
  "$PY" "$KIT/scripts/hot_cap_check.py" --root "$ROOT" || true
else
  echo "  ⚠️  技能里没有 scripts/hot_cap_check.py（v2.0.2 新增件，还没落地）—— 本步跳过"
fi

printf '\n✅ 收工通过：前五步全绿\n'
