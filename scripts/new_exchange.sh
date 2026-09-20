#!/usr/bin/env bash
# 建一个受控交流测试目录：<root>/exchange/<YYYY-MM-DD-主题>/{task.md, answer.md}
#
# 协议的分工（详见 <root>/exchange/README.md）：
#   出题方写 task.md；answer.md **建出来就是空的**；
#   作答方只写 answer.md；复核与记忆由出题方写。
#
# 用法：
#   bash new_exchange.sh "2026-09-21-本地库口径抽测" "一句话说明"
#   bash new_exchange.sh --root /path/ws "..." "..."
#   ISSUER=teammate-x bash new_exchange.sh "..." "..."
# 退出码：0 成功；2 已存在；3 模板缺失；4 目录名不合规
set -euo pipefail

KIT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROOT="${MEM_KIT_ROOT:-}"
ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) ROOT="${2:?--root 需要路径}"; shift 2 ;;
    --root=*) ROOT="${1#--root=}"; shift ;;
    *) ARGS+=("$1"); shift ;;
  esac
done
if [[ -z "$ROOT" ]]; then
  d="$PWD"
  while [[ "$d" != "/" ]]; do
    if [[ -f "$d/.memory-kit.toml" || ( -f "$d/AGENTS.md" && -d "$d/memory" ) ]]; then ROOT="$d"; break; fi
    d=$(dirname "$d")
  done
  ROOT="${ROOT:-$PWD}"
fi

SLUG="${ARGS[0]:?用法: new_exchange.sh [--root DIR] \"YYYY-MM-DD-主题\" \"一句话说明\"}"
NOTE="${ARGS[1]:-（未填一句话说明）}"
ISSUER="${ISSUER:-lead}"
# 目录名按时间（YYYY-MM-DD-主题）—— 体检按这条判命名，脚手架必须先拦，不然会立刻造出 ❌
if [[ ! "$SLUG" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}-.+ ]]; then
  echo "!! 目录名要按时间：YYYY-MM-DD-主题（收到：$SLUG）" >&2
  echo "   例：bash new_exchange.sh \"$(date '+%Y-%m-%d')-本地库口径抽测\" \"一句话说明\"" >&2
  exit 4
fi
DIR="$ROOT/exchange/$SLUG"
TPL="$ROOT/exchange/_TEMPLATE"
[[ -d "$TPL" ]] || TPL="$KIT_DIR/../templates/exchange/_TEMPLATE"   # 没铺模板就用技能自带的
[[ -d "$TPL" ]] || { echo "!! 模板目录不存在：$TPL（先跑 bootstrap.sh 或检查技能安装）" >&2; exit 3; }
if [[ -e "$DIR" ]]; then
  echo "!! 已存在（同类测试请在该目录内追加 task-2.md/answer-2.md）：$DIR" >&2
  exit 2
fi

mkdir -p "$DIR"
sed -e "s|{{主题}}|$SLUG|g" -e "s|<主题>|$SLUG|g" \
    -e "s|{{说明}}|$NOTE|g" -e "s|<说明>|$NOTE|g" \
    -e "s|^出题方: .*|出题方: $ISSUER|" \
    -e "s|^出题时间: .*|出题时间: $(date '+%Y-%m-%d %H:%M %z')|" \
    "$TPL/task.md" > "$DIR/task.md"
cp "$TPL/answer.md" "$DIR/answer.md"

echo "已创建：$DIR"
echo "  task.md    ← 出题方写（补完占位、写清验收标准）"
echo "  answer.md  ← 空答复文档，只有作答方写"
echo
echo "给作答方的提示（原样转发即可）："
echo "  只写 $DIR/answer.md，其它文件别动（这样谁改了什么一目了然）；"
echo "  写清：结论 + 依据（命令/原始输出）+ 不确定处；卡住就在 answer.md 里写明卡点后停止。"
