#!/usr/bin/env bash
# 在一个工作区里铺开记忆制度：目录 + 各区 README + 配置 + 脚本薄壳。
# **默认六区**（memory/handbook/exchange/scratch/archive/trash），可用 --areas 加挂
# （如 projects = 要长期维护的项目、data = 机器用的大文件活库）。
#
# 用法：
#   bash bootstrap.sh                             # 当前目录
#   bash bootstrap.sh --root /path/to/ws          # 指定工作区
#   bash bootstrap.sh --root . --preset hithink   # 附带同花顺本地库采集器
#   bash bootstrap.sh --root . --name 我的工作区 --force
#   bash bootstrap.sh --root . --areas memory,handbook,exchange,scratch,projects,archive,trash,data
#       # 加挂区必须有同名模板 templates/areas/<区>/README.md；顺序即写入 .memory-kit.toml 的顺序
#
# 原则：**只补不覆盖**。已存在的文件默认跳过（--force 时先备份成 *.bak-<时间戳>）。
# 退出码：0 成功；2 用法错。
set -euo pipefail

KIT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
TPL="$KIT/templates"
STAMP=$(date '+%Y%m%d-%H%M%S')
ROOT=""; PRESET="none"; NAME=""; FORCE=0; AREAS_CSV=""
AREAS_DEFAULT="memory handbook exchange scratch archive trash"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) ROOT="${2:?--root 需要路径}"; shift 2 ;;
    --root=*) ROOT="${1#--root=}"; shift ;;
    --preset) PRESET="${2:?--preset 需要值}"; shift 2 ;;
    --preset=*) PRESET="${1#--preset=}"; shift ;;
    --name) NAME="${2:?--name 需要值}"; shift 2 ;;
    --name=*) NAME="${1#--name=}"; shift ;;
    --areas) AREAS_CSV="${2:?--areas 需要逗号分隔的区名}"; shift 2 ;;
    --areas=*) AREAS_CSV="${1#--areas=}"; shift ;;
    --force) FORCE=1; shift ;;
    -h|--help) sed -n '2,15p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "!! 未知参数：$1" >&2; exit 2 ;;
  esac
done
ROOT="${ROOT:-$PWD}"
[[ -d "$ROOT" ]] || { echo "!! 工作区不存在：$ROOT" >&2; exit 2; }
ROOT=$(cd "$ROOT" && pwd)
NAME="${NAME:-$(basename "$ROOT")}"
case "$PRESET" in
  none|dsh|hithink) ;;
  *) echo "!! 未知 preset：$PRESET（可选 none|dsh|hithink）" >&2; exit 2 ;;
esac

# 区清单：默认六区；加挂区必须有模板，否则早失败（别铺出半套制度）
if [[ -n "$AREAS_CSV" ]]; then AREAS="${AREAS_CSV//,/ }"; else AREAS="$AREAS_DEFAULT"; fi
for a in $AREAS; do
  [[ -f "$TPL/areas/$a/README.md" ]] \
    || { echo "!! 没有模板：templates/areas/$a/README.md（可用区：$(ls "$TPL/areas" | tr '\n' ' '))" >&2; exit 2; }
done
AREAS_TOML=$(printf '"%s", ' $AREAS); AREAS_TOML="[${AREAS_TOML%, }]"

put() { # put <模板文件> <目标文件>
  local src="$1" dst="$2"
  mkdir -p "$(dirname "$dst")"
  if [[ -e "$dst" ]]; then
    if [[ $FORCE -eq 1 ]]; then
      cp -p "$dst" "$dst.bak-$STAMP"; echo "  覆盖（已备份 $dst.bak-$STAMP）"
    else
      echo "  跳过（已存在）：${dst#$ROOT/}"; return 0
    fi
  else
    echo "  新增：${dst#$ROOT/}"
  fi
  sed -e "s|{{工作区}}|$NAME|g" \
      -e "s|{{一句话定位}}|（待填：一句话说明这个工作区在做什么）|g" \
      -e "s|{{日期}}|$(date '+%Y-%m-%d')|g" "$src" > "$dst"
}

echo "== 铺开记忆制度 =="
echo "工作区：$ROOT"
echo "工作区名：$NAME　preset：$PRESET"
echo "区（$(( $(echo $AREAS | wc -w) )) 个）：$AREAS"
for area in $AREAS; do
  mkdir -p "$ROOT/$area"
  put "$TPL/areas/$area/README.md" "$ROOT/$area/README.md"
done

put "$TPL/memory-settings.md"      "$ROOT/memory/settings.md"
put "$TPL/exchange/task.md"        "$ROOT/exchange/_TEMPLATE/task.md"
put "$TPL/exchange/answer.md"      "$ROOT/exchange/_TEMPLATE/answer.md"
# 注意：模板文件叫 AGENTS.md.tmpl，**不能**直接以 AGENTS.md 存进 templates/ ——
# 否则把这棵树放进工作区时，harness 会把这份"带占位符的模板"当成工作区指令注入。
put "$TPL/AGENTS.md.tmpl"          "$ROOT/AGENTS.md"

# 项目配置文件（含 preset 差异）
CFG="$ROOT/.memory-kit.toml"
if [[ -e "$CFG" && $FORCE -eq 0 ]]; then
  echo "  跳过（已存在）：.memory-kit.toml"
else
  [[ -e "$CFG" ]] && { cp -p "$CFG" "$CFG.bak-$STAMP"; echo "  覆盖（已备份 .memory-kit.toml.bak-$STAMP）"; }
  COLLECTORS='collectors = []'
  DEPS='deps = ["AGENTS.md"]'
  TOOLS='tools = []'
  if [[ "$PRESET" == "dsh" || "$PRESET" == "hithink" ]]; then
    COLLECTORS='collectors = ["scratch/memory-tooling/collectors/dsh_routes.py"]'
  fi
  if [[ "$PRESET" == "hithink" ]]; then
    COLLECTORS='collectors = [
  "scratch/memory-tooling/collectors/hithink_market_db.py",
  "scratch/memory-tooling/collectors/dsh_routes.py",
]'
    DEPS='deps = ["AGENTS.md", "~/.local/share/hithink-finance/market.duckdb"]'
    TOOLS='tools = ["hithink-finance"]'
  fi
  cat > "$CFG" <<EOF
# 记忆制度配置 —— agent-memory-kit 读它（tomllib，只读），手改即可生效。
# 全部字段都有内置默认值；这里只写本工作区要覆盖的部分。

areas = $AREAS_TOML

[limits]
max_hot_lines = 70          # AGENTS.md 行数上限（热记忆要短）
max_note_lines = 150        # 单篇笔记/手册硬上限：超过必须压缩
tldr_min_lines = 80         # 超过这么多行，开头必须有「结论」
tldr_head_lines = 12
state_max_age_days = 7      # STATE.md 多久算过期
pending_max_age_days = 3    # 交流测试 pending 多久提醒催办
handbook_max_age_days = 90  # handbook「最后验证」多久提醒复审

[secrets]
# 允许出现敏感串的文件（按**基名**匹配）。默认空 = 一律 ❌。
# 只有在「确有必要 + 该文件已被明确限定用途」时才加，例如：
#   allow_files = ["settings.md"]   # 环境事实区，用户已确认只该它放 Key
allow_files = []

[scan]
# 体检/采集时**整棵跳过**的路径（相对工作区根）。默认空。
# 用于工作区里放了"别处的树"（技能/模板仓库的检出）—— 它的相对链接按自己的布局解析，
# 当工作区文档体检必然全断。**只排除外来树**，不要拿它掩盖自己文档的真实断链。
exclude = []

[state]
# STATE.md 的采集器：每个 .py 暴露 collect(root, cfg) -> list[str]
# 自加采集器：放 scratch/memory-tooling/collectors/*.py，再把路径登记到这里
$COLLECTORS
# 这些文件比 STATE.md 新 → 提示重新生成
$DEPS
# 工具版本要打印哪些 CLI（--version 输出）
$TOOLS
EOF
  echo "  写入：.memory-kit.toml（preset=$PRESET，areas=$AREAS_TOML）"
fi

# 脚本薄壳：命令入口留在工作区，实现只有一份（在技能里）
SHIM="$ROOT/scratch/memory-tooling"
mkdir -p "$SHIM"
sed -e "s|{{KIT}}|$KIT|g" "$TPL/shim/memory_doctor.py"   > "$SHIM/memory_doctor.py"
sed -e "s|{{KIT}}|$KIT|g" "$TPL/shim/state_snapshot.py"  > "$SHIM/state_snapshot.py"
sed -e "s|{{KIT}}|$KIT|g" "$TPL/shim/new_exchange.sh"    > "$SHIM/new_exchange.sh"
sed -e "s|{{工作区}}|$NAME|g" "$TPL/shim/README.md"      > "$SHIM/README.md"
chmod +x "$SHIM/new_exchange.sh"
echo "  写入：scratch/memory-tooling/（薄壳 + 说明）"

if [[ "$PRESET" == "hithink" ]]; then
  mkdir -p "$SHIM/collectors"
  cp "$KIT/scripts/collectors/hithink_market_db.py" "$SHIM/collectors/"
  echo "  写入：scratch/memory-tooling/collectors/hithink_market_db.py"
fi
mkdir -p "$SHIM/collectors"
cp "$KIT/scripts/collectors/dsh_routes.py" "$SHIM/collectors/"
echo "  写入：scratch/memory-tooling/collectors/dsh_routes.py"

if command -v python3 >/dev/null 2>&1; then
  echo "  生成第一份 STATE.md ..."
  python3 "$SHIM/state_snapshot.py" --root "$ROOT" || echo "  !! STATE.md 生成失败（稍后手动跑 state_snapshot.py）"
fi

echo
echo "== 下一步 =="
echo "  1) 补 AGENTS.md 的「一句话定位」，并填 memory/README.md 的索引表"
echo "  2) 体检：python3 scratch/memory-tooling/memory_doctor.py   （❌ 要清零）"
echo "  3) 出第一道交流测试：bash scratch/memory-tooling/new_exchange.sh \"$(date '+%Y-%m-%d')-主题\" \"说明\""
echo "  4) 数据/盘/配置变动后：python3 scratch/memory-tooling/state_snapshot.py"
