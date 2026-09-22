#!/usr/bin/env bash
# 在一个工作区里铺开记忆制度：目录 + 各区 README + 配置 + 脚本薄壳 + 索引。
#
# **只依赖两样大伙都有的东西**：一个 POSIX shell（跑本脚本）和一个 Python 3（跑脚本，标准库就够）。
# 不装任何第三方包、不调用任何外部 CLI（需要外部命令的采集器由你自己判断"在不在"）。
#
# 用法：
#   bash bootstrap.sh                             # 当前目录
#   bash bootstrap.sh --root /path/to/ws          # 指定工作区
#   bash bootstrap.sh --root . --name 我的工作区 --force
#   bash bootstrap.sh --root . --areas memory,handbook,exchange,scratch,projects,archive,trash,data
#       # 加挂区必须有同名模板 templates/areas/<区>/README.md；顺序即写入 .memory-kit.toml 的顺序
#   bash bootstrap.sh --root . --collector /path/to/my_collector.py
#       # 额外带一个 STATE 采集器（可重复）；技能只自带一个通用示例 example.py
#
# 原则：**只补不覆盖**。已存在的文件默认跳过（--force 时先备份成 *.bak-<时间戳>）。
# 退出码：0 成功；2 用法错。
set -euo pipefail

KIT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
TPL="$KIT/templates"
STAMP=$(date '+%Y%m%d-%H%M%S')
ROOT=""; NAME=""; FORCE=0; AREAS_CSV=""; COLLECTORS_ARG=()
AREAS_DEFAULT="memory handbook exchange scratch archive trash"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root) ROOT="${2:?--root 需要路径}"; shift 2 ;;
    --root=*) ROOT="${1#--root=}"; shift ;;
    --name) NAME="${2:?--name 需要值}"; shift 2 ;;
    --name=*) NAME="${1#--name=}"; shift ;;
    --areas) AREAS_CSV="${2:?--areas 需要逗号分隔的区名}"; shift 2 ;;
    --areas=*) AREAS_CSV="${1#--areas=}"; shift ;;
    --collector) COLLECTORS_ARG+=("${2:?--collector 需要文件路径}"); shift 2 ;;
    --collector=*) COLLECTORS_ARG+=("${1#--collector=}"); shift ;;
    --force) FORCE=1; shift ;;
    -h|--help) sed -n '2,19p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "!! 未知参数：$1" >&2; exit 2 ;;
  esac
done
ROOT="${ROOT:-$PWD}"
[[ -d "$ROOT" ]] || { echo "!! 工作区不存在：$ROOT" >&2; exit 2; }
ROOT=$(cd "$ROOT" && pwd)
NAME="${NAME:-$(basename "$ROOT")}"

# 区清单：默认六区；加挂区必须有模板，否则早失败（别铺出半套制度）
if [[ -n "$AREAS_CSV" ]]; then AREAS="${AREAS_CSV//,/ }"; else AREAS="$AREAS_DEFAULT"; fi
for a in $AREAS; do
  [[ -f "$TPL/areas/$a/README.md" ]] \
    || { echo "!! 没有模板：templates/areas/$a/README.md（可用区：$(ls "$TPL/areas" | tr '\n' ' '))" >&2; exit 2; }
done
AREAS_TOML=$(printf '"%s", ' $AREAS); AREAS_TOML="[${AREAS_TOML%, }]"
# 结构化台账默认覆盖"除 data 外的区"（data 是机器大文件，不是记忆）
IDX=""; for a in $AREAS; do [[ "$a" == "data" ]] && continue; IDX="$IDX \"$a\","; done
INDEX_ZONES="[${IDX%, }]"

# 额外采集器（可重复）：清点文件是否存在，并预生成配置里的列表
if [[ ${#COLLECTORS_ARG[@]} -gt 0 ]]; then
  for c in "${COLLECTORS_ARG[@]}"; do
    [[ -f "$c" ]] || { echo "!! 采集器不存在：$c" >&2; exit 2; }
  done
fi

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
echo "工作区名：$NAME"
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

# 项目配置文件
CFG="$ROOT/.memory-kit.toml"
if [[ -e "$CFG" && $FORCE -eq 0 ]]; then
  echo "  跳过（已存在）：.memory-kit.toml"
else
  [[ -e "$CFG" ]] && { cp -p "$CFG" "$CFG.bak-$STAMP"; echo "  覆盖（已备份 .memory-kit.toml.bak-$STAMP）"; }
  COLLECTORS='collectors = []'
  if [[ ${#COLLECTORS_ARG[@]} -gt 0 ]]; then
    COLLECTORS='collectors = ['
    for c in "${COLLECTORS_ARG[@]}"; do
      COLLECTORS="$COLLECTORS
  \"scratch/memory-tooling/collectors/$(basename "$c")\","
    done
    COLLECTORS="$COLLECTORS
]"
  fi
  cat > "$CFG" <<EOF
# 记忆制度配置 —— agent-memory-kit 读它（只读）。有 tomllib 就用，没有就用内置极简 TOML 解析。
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

[index]
# 结构化台账（**数据，不参与 md 行数/断链规则**）：memory → memory/index/YYYY-MM.json；其他区 → <区>/index.json
zones = $INDEX_ZONES
budget_lines = 6000     # 正文总量预算（阅读面）：超了体检提醒"该结账了"
live_days = 7           # 各区 README 活窗口：近 N 天
live_rows = 12          # 活窗口最多显示多少行（有界，防 README 再膨胀）

[state]
# STATE.md 的采集器：每个 .py 暴露 collect(root, cfg) -> list[str]
# 自加采集器：放 scratch/memory-tooling/collectors/*.py，再把路径登记到这里
$COLLECTORS
# 这些文件比 STATE.md 新 → 提示重新生成
deps = ["AGENTS.md"]
# 工具版本要打印哪些 CLI（--version 输出）；留空 = 不调用任何外部命令
tools = []
EOF
  echo "  写入：.memory-kit.toml（areas=$AREAS_TOML）"
fi

# 脚本薄壳：命令入口留在工作区，实现只有一份（在技能里）
SHIM="$ROOT/scratch/memory-tooling"
mkdir -p "$SHIM"
sed -e "s|{{KIT}}|$KIT|g" "$TPL/shim/memory_doctor.py"   > "$SHIM/memory_doctor.py"
sed -e "s|{{KIT}}|$KIT|g" "$TPL/shim/state_snapshot.py"  > "$SHIM/state_snapshot.py"
sed -e "s|{{KIT}}|$KIT|g" "$TPL/shim/memory_query.py"    > "$SHIM/memory_query.py"
sed -e "s|{{KIT}}|$KIT|g" "$TPL/shim/new_exchange.sh"    > "$SHIM/new_exchange.sh"
sed -e "s|{{工作区}}|$NAME|g" "$TPL/shim/README.md"      > "$SHIM/README.md"
chmod +x "$SHIM/new_exchange.sh"
echo "  写入：scratch/memory-tooling/（4 个薄壳 + 说明）"

# 采集器：技能只带一个**通用示例**；项目专用的一律由 --collector 从外面带进来
mkdir -p "$SHIM/collectors"
cp "$KIT/scripts/collectors/example.py" "$SHIM/collectors/example.py"
echo "  写入：scratch/memory-tooling/collectors/example.py（示例，默认未登记）"
if [[ ${#COLLECTORS_ARG[@]} -gt 0 ]]; then
  for c in "${COLLECTORS_ARG[@]}"; do
    cp "$c" "$SHIM/collectors/$(basename "$c")"
    echo "  写入：scratch/memory-tooling/collectors/$(basename "$c")"
  done
fi

if command -v python3 >/dev/null 2>&1; then
  echo "  生成第一份 STATE.md ..."
  python3 "$SHIM/state_snapshot.py" --root "$ROOT" || echo "  !! STATE.md 生成失败（稍后手动跑 state_snapshot.py）"
  echo "  建索引（memory/index/*.json、<区>/index.json）+ 刷新各区 README 活窗口 ..."
  python3 "$SHIM/memory_query.py" --root "$ROOT" --rebuild --zone all >/dev/null \
    && python3 "$SHIM/memory_query.py" --root "$ROOT" --refresh --zone all >/dev/null \
    || echo "  !! 索引生成失败（稍后手动跑 memory_query.py --rebuild --refresh）"
else
  echo "  !! 没找到 python3 —— 体检/STATE/索引脚本都跑不了；装一个 Python 3 再来"
fi

echo
echo "== 下一步 =="
echo "  1) 补 AGENTS.md 的「一句话定位」（**不用**再往 memory/README.md 加索引行 —— 台账在 index.json）"
echo "  2) 体检：python3 scratch/memory-tooling/memory_doctor.py   （❌ 要清零）"
echo "  3) 写/删笔记后：python3 scratch/memory-tooling/memory_query.py --rebuild --refresh"
echo "  4) 出第一道交流测试：bash scratch/memory-tooling/new_exchange.sh \"$(date '+%Y-%m-%d')-主题\" \"说明\""
echo "  5) 数据/盘/配置变动后：python3 scratch/memory-tooling/state_snapshot.py"
echo "  6) 阅读面收不住了（--stats 超预算）：memory_query.py --prune --before <日期> --apply"
