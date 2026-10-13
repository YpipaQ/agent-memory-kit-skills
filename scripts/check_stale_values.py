#!/usr/bin/env python3
"""失效硬值扫描 —— 文档里点名的**绝对／家目录路径**还成不成立。

用途：压缩（或任何逐条点名核对）时顺手做"有效性复核"。小样首例的教训：机械核对该只查
「值有没有保留」，查不出「值还成不成立」—— 笔记里的技能路径 `project/office-docs/` 早已改名，
"保留"得好好的，却指不到任何东西。

用法：
  python3 check_stale_values.py [--root <工作区>] [--baseline <路径>] [--json]
  python3 check_stale_values.py --refresh-baseline     # 重写基线（保留既有理由；新增项没理由就拒写）

四档：**未声明**（问题，活指针该修）／**已声明**（行内有"不存在/已改名/别写死"等字样，
或用 `~~…~~` 标过）／**基线已接受**（历史记录与存档，理由写在基线文件里）／其他（路径还在，无事）。
严重度分区：`[stale] strict_zones` 里（AGENTS.md、.memory-kit.toml、memory/settings.md、
handbook/、projects/）的未声明 → **❌ 且退出 1**；其余区的未声明（日期笔记/交流/试验）→ 仅 ⚠️。

退出码：0 = 严区没有未声明失效；1 = 有（或 --refresh-baseline 拒绝写盘）；2 = 用法错。

边界：
  - 只查**绝对路径与 `~/` 路径**，且只认已知文件系统根（`_common.FS_PATH_ROOTS`：
    `~ /home /etc /var /usr /opt /mnt /ias /srv /root`）—— 相对路径不查（基准不唯一）；
    URL/API 路由天然不会命中这一条。
  - 跳过含通配/占位/歧义写法的（`*{}<>…$[]|`、`/path`、`...`）；`~~…~~` 包裹的算**已声明**。
  - 扫描面：根 `*.md` ＋ `.memory-kit.toml` ＋ 区（默认 memory,handbook,projects,exchange,scratch）；
    **整棵排除 `trash/`、`data/`**（存档与活库不判活指针）。
  - **跳过自动生成的活窗口区块**（`<!-- index:start … -->` … `<!-- index:end -->`，契约 §9）：
    那是区 README 里的派生副本（源头在笔记/条目），判它没意义 —— 否则笔记一条非严区死链
    会被抄进严区 README 再报一次 ❌。
  - 基线路径的解析：`--baseline` 给的**相对路径按当前目录**（cwd）解析；配置 `[stale] baseline` 里的
    相对路径按**工作区根**解析。
  - 不判"该不该修"：历史记录里的死链本就可能是对的，由人点名并写进基线理由。
  - **平台边界（2026-10-14）**：路径按**当前平台形态**过滤 —— POSIX 上跳过 `C:\…`，Windows 上跳过 `/…`；
    当前路径根集合是 POSIX 形态 ⇒ **在 Windows 上等于不扫**（不报错、也不误报）。
    要真跨平台需补盘符根与 `%USERPROFILE%`（已知限制，见归档包里的决议单 D3）。

供 `memory_doctor.py` 复用：`scan(root, cfg)` 与 `classify(root, cfg, hits)`。
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import date
from pathlib import Path

sys.dont_write_bytecode = True            # 不在工作区里留 __pycache__（要在 import _common 之前）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import FS_PATH_ROOTS, load_config, resolve_root  # noqa: E402

# 路径根的"交替式"**取自 `_common.FS_PATH_ROOTS`**（与 check_hard_values 同一口径，禁止各定义一套）
_ROOT_ALT = "|".join(re.escape(r) for r in FS_PATH_ROOTS if r != "~")
# 只认**已知文件系统根**：把 API 路由/URL/相对路径全排除（首版 315 误报 → 34）
PATH_RE = re.compile(
    r"(?<![\w\u4e00-\u9fff./\\-])"                       # 左边不能是词字符/点/斜杠/连字符
    r"(~(?:/[\w\u4e00-\u9fff@.+\-]+)+"                   # ~/...
    r"|(?:" + _ROOT_ALT + r")(?:/[\w\u4e00-\u9fff@.+\-]+)+)"
)
SKIP_CHARS = set("*{}<>…$[]|")
# 扫描面（契约 §4.1）：区默认就这 5 个；trash/、data/ 是存档与活库，不判活指针
STALE_ZONES = ("memory", "handbook", "projects", "exchange", "scratch")
EXCLUDE_ZONES = ("trash", "data")
ROOT_EXTRA_FILES = (".memory-kit.toml",)
DECLARED_MARKERS = ["不存在", "已失效", "已改名", "已退役", "已删除", "已搬", "已挪",
                    "别写死", "不要写死", "曾经", "原本", "一度", "旧名", "原路径"]
BASELINE_NOTE = ("已接受的历史失效路径（每条带理由）。**基线要随事实重生成**："
                 "事实一变就重跑扫描并刷新本文件，别让它自己变成过期记录。")
# `memory_query.py --refresh` 生成的**活窗口**区块（契约 §9）：派生副本不判活指针 ——
# 否则笔记里一条非严区死链会被抄进 `<区>/README.md`，而 handbook/、projects/ 是严区 ⇒ 同一处报两次 ❌，
# 逼人去改一个写着"勿手改"的文件。修源头才有意义。
LIVE_START = "<!-- index:start"
LIVE_END = "<!-- index:end"


def _skip(p: str) -> bool:
    """跳过不够"确指"的写法（通配/占位/歧义/裸目录）—— 免得拿噪声掩盖真问题。"""
    if any(c in p for c in SKIP_CHARS):
        return True
    bare = {"", "/", "~", "/path", "/tmp"} | {r for r in FS_PATH_ROOTS if r != "~"}
    if p.rstrip("/") in bare:
        return True
    if "..." in p or p.endswith((".", "-", "/")):
        return True
    # 平台形态过滤（v2.0.2）：**不检查"本平台不可能存在的形态"**，免得把别处平台的路径判成失效。
    # POSIX 上跳过盘符路径（`C:\…`）；Windows 上跳过以 `/` 开头的路径。
    # 这样最坏是"没覆盖"，绝不会"假报失效"；当前路径根集合是 POSIX 形态 ⇒ Windows 上等于不扫（见文档"平台边界"）。
    if os.name != "nt" and re.match(r"^[A-Za-z]:[\\/]", p):
        return True
    if os.name == "nt" and p.startswith("/"):
        return True
    return False


def _rel(root: Path, f: Path) -> str:
    try:
        return f.relative_to(root).as_posix()
    except ValueError:
        return str(f)


def _iter_files(root: Path) -> list[Path]:
    files: list[Path] = []
    try:
        files.extend(sorted(p for p in root.iterdir() if p.is_file() and p.suffix.lower() == ".md"))
    except OSError:
        pass
    for name in ROOT_EXTRA_FILES:
        p = root / name
        if p.is_file():
            files.append(p)
    for z in STALE_ZONES:
        if z in EXCLUDE_ZONES:
            continue
        base = root / z
        if not base.is_dir():
            continue
        for f in sorted(base.rglob("*.md")):
            parts = f.relative_to(root).parts
            if parts and parts[0] in EXCLUDE_ZONES:
                continue
            files.append(f)
    return files


def _scan_lines(text: str):
    """逐行产出 `(行号, 行)`，但**整块跳过活窗口**（`<!-- index:start … -->` … `<!-- index:end -->`）。

    区块是 `memory_query.py --refresh` 生成的派生副本（文件里自带"勿手改"提示）：
    源头在笔记/条目里，派生副本不判活指针。区块没闭合就一直跳到文件尾（宁可少报派生副本）。
    """
    in_block = False
    for n, line in enumerate(text.splitlines(), 1):
        has_start = LIVE_START in line
        has_end = LIVE_END in line
        if in_block:
            if has_end:
                in_block = False
            continue
        if has_start:
            in_block = not has_end          # start/end 同行 = 空区块，也算跳过
            continue
        yield n, line


def scan(root: Path, cfg: dict) -> list[dict]:
    """扫出所有绝对/家目录路径命中（**原始命中**，未去重、未分档）。

    每条：`{file, line, path, exists, declared, context}`；`declared` 已把"行内有 markers"与
    "`~~…~~` 标注"合并进来（`~~` 是作者的明确标记 ⇒ 归"已声明"，只提醒不算失败）。
    自动生成的**活窗口区块**（`<!-- index:start … -->` … `<!-- index:end -->`）整体跳过 —— 那是派生副本。
    """
    markers = [str(m) for m in ((cfg.get("stale") or {}).get("markers") or DECLARED_MARKERS)]
    home = Path(os.path.expanduser("~"))
    hits: list[dict] = []
    for f in _iter_files(root):
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = _rel(root, f)
        for n, line in _scan_lines(text):
            struck = [m.span() for m in re.finditer(r"~~[^~]+~~", line)]
            line_declared = any(k in line for k in markers)
            for m in PATH_RE.finditer(line):
                in_struck = any(a <= m.start() < b for a, b in struck)
                raw = m.group(1).rstrip("）)。，,;；:：'\"")
                if _skip(raw):
                    continue
                target = home / raw[2:] if raw.startswith("~/") else Path(raw)
                try:
                    exists = target.exists()
                except OSError:
                    exists = False
                hits.append({
                    "file": rel,
                    "line": n,
                    "path": raw,
                    "exists": exists,
                    "declared": bool(in_struck or line_declared),
                    "context": line.strip()[:110],
                })
    return hits


def _strict(rel: str, cfg: dict) -> bool:
    """命中是否落在严区（活指针）。`handbook/` 这类带斜杠的按**目录前缀**，其余按**精确文件**。"""
    for z in ((cfg.get("stale") or {}).get("strict_zones") or []):
        zz = str(z).strip().rstrip("/")
        if not zz:
            continue
        if rel == zz or rel.startswith(zz + "/"):
            return True
    return False


def baseline_path(root: Path, cfg: dict, override: str | None = None) -> Path | None:
    if override:
        return Path(override).expanduser()
    b = str((cfg.get("stale") or {}).get("baseline") or "").strip()
    if not b:
        return None
    p = Path(b).expanduser()
    return p if p.is_absolute() else (root / p)


def load_baseline(p: Path | None) -> list[dict]:
    """读基线；**容忍格式差异**（`{"accepted":[...]}` / `{"entries":[...]}` / 裸 list）。坏文件=空。"""
    if p is None or not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if isinstance(data, dict):
        data = data.get("accepted") or data.get("entries") or []
    if not isinstance(data, list):
        return []
    out: list[dict] = []
    for e in data:
        if not isinstance(e, dict):
            continue
        f_, p_ = str(e.get("file", "")).strip(), str(e.get("path", "")).strip()
        if f_ and p_:
            out.append({"file": f_, "path": p_, "reason": str(e.get("reason", "")).strip()})
    return out


def classify(root: Path, cfg: dict, hits: list[dict], baseline: str | None = None) -> dict:
    """把命中分档 —— 只对**失效**（路径不存在）的条目分档；路径还在的算"其他"，不进结果。

    返回 `{"scanned", "undeclared", "declared", "accepted"}`；`undeclared` 每条带 `strict: bool`
    （doctor 靠它决定严区 ❌ / 非严区 ⚠️）。分档优先级：基线已接受 ＞ 已声明 ＞ 未声明。
    可选 `baseline` 覆盖配置文件里的基线路径（CLI `--baseline` 用）。
    """
    entries = load_baseline(baseline_path(root, cfg, baseline))
    accepted_keys = {(e["file"], e["path"]) for e in entries}
    reasons = {(e["file"], e["path"]): e["reason"] for e in entries}

    seen: set[tuple[str, str]] = set()
    undeclared: list[dict] = []
    declared: list[dict] = []
    accepted: list[dict] = []
    for h in hits:
        if h["exists"]:
            continue
        key = (h["file"], h["path"])
        if key in seen:
            continue
        seen.add(key)
        item = dict(h)
        item["strict"] = _strict(h["file"], cfg)
        if key in accepted_keys:
            item["reason"] = reasons.get(key, "")
            accepted.append(item)
        elif h["declared"]:
            declared.append(item)
        else:
            undeclared.append(item)
    return {"scanned": len(hits), "undeclared": undeclared,
            "declared": declared, "accepted": accepted}


def _print_lines(items: list[dict]) -> None:
    for h in items:
        print(f"  {h['file']}:{h['line']}  {h['path']}")


def _refresh(root: Path, cfg: dict, override: str | None, res: dict) -> int:
    """重写基线：保留既有理由；**新增未声明项没有理由就拒绝写盘并列出**。"""
    bpath = baseline_path(root, cfg, override)
    if bpath is None:
        print("❌ 既没配 [stale] baseline，也没给 --baseline <路径>，无法刷新", file=sys.stderr)
        return 2
    old = load_baseline(bpath)
    old_keys = {(e["file"], e["path"]) for e in old}
    noreason = [e for e in old if not e["reason"]]
    new_items = [h for h in res["undeclared"] if (h["file"], h["path"]) not in old_keys]
    if noreason or new_items:
        print(f"❌ 拒绝写盘：{bpath}")
        for e in noreason:
            print(f"  基线条目缺理由：{e['file']}  {e['path']}")
        for h in new_items:
            zone = "严区" if h.get("strict") else "非严区"
            print(f"  新增未声明项（{zone}，无理由）：{h['file']}:{h['line']}  {h['path']}")
        print('  补理由：在基线 accepted 里加 {"file","path","reason"} 再重跑；'
              "或把行内改成已声明（行内加「已改名/不存在/别写死…」或 `~~路径~~`）")
        return 1

    still_dead = {(h["file"], h["path"]) for h in res["undeclared"] + res["declared"] + res["accepted"]}
    kept = [e for e in old if (e["file"], e["path"]) in still_dead]
    dropped = len(old) - len(kept)
    payload = {"note": BASELINE_NOTE, "updated": date.today().isoformat(), "accepted": kept}
    try:
        bpath.parent.mkdir(parents=True, exist_ok=True)
        bpath.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    except OSError as e:
        print(f"❌ 写盘失败：{bpath}（{e}）", file=sys.stderr)
        return 1
    print(f"✅ 已重写基线：{bpath}（保留 {len(kept)} 条理由，剪掉已不再失效 {dropped} 条）")
    return 0


def main(argv: list[str]) -> int:
    argv = list(argv)
    as_json = "--json" in argv
    refresh = "--refresh-baseline" in argv
    override = None
    if "--baseline" in argv:
        i = argv.index("--baseline")
        if i + 1 >= len(argv):
            print("用法错：--baseline 后面要接路径", file=sys.stderr)
            return 2
        override = argv[i + 1]
    root = resolve_root(argv)
    if not root.is_dir():
        print(f"工作区根不存在：{root}", file=sys.stderr)
        return 2
    cfg = load_config(root)

    hits = scan(root, cfg)
    res = classify(root, cfg, hits, override)
    undeclared, declared, accepted = res["undeclared"], res["declared"], res["accepted"]
    strict_und = [h for h in undeclared if h.get("strict")]
    loose_und = [h for h in undeclared if not h.get("strict")]

    if refresh:
        return _refresh(root, cfg, override, res)

    if as_json:
        print(json.dumps({"scanned": res["scanned"], "undeclared": undeclared,
                          "declared": declared, "accepted": accepted},
                         ensure_ascii=False, indent=1))
        return 1 if strict_und else 0

    total_dead = len(undeclared) + len(declared) + len(accepted)
    print(f"扫到绝对/家目录路径 {res['scanned']} 处（去重后失效 {total_dead} 处："
          f"未声明 {len(undeclared)}、已声明 {len(declared)}、基线已接受 {len(accepted)}）")
    if accepted:
        print(f"\n· 基线已接受 {len(accepted)} 处（历史记录/存档，理由在基线文件里）：")
        _print_lines(accepted)
    if declared:
        print(f"\n⚠️ 已声明失效 {len(declared)} 处（行内有 markers 或用 `~~…~~` 标过）—— 逐条扫一眼即可：")
        _print_lines(declared)
    if strict_und:
        print(f"\n❌ 严区未声明失效 {len(strict_und)} 处（活指针该修）：")
        _print_lines(strict_und)
    if loose_und:
        print(f"\n⚠️ 非严区未声明失效 {len(loose_und)} 处（历史记录看得见即可，要留就写进基线）：")
        _print_lines(loose_und)
    if not undeclared:
        print("\n✅ 没有未声明的失效路径")
    return 1 if strict_und else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
