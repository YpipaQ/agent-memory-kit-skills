#!/usr/bin/env python3
"""记忆索引 + 圈定范围检索 —— **索引与散文分离**。

为什么有它：旧规则要求"每篇笔记必须在 README 里列一行"，README 就随笔记数无限膨胀，
迟早撞死 md 硬上限（实测：按 18 篇/天的强度，5 天撞 150 行、8 天撞 200 行）。
现在改成：**台账进 JSON（数据，不参与 md 行数/断链规则）、README 只留规则与活窗口、检索交给程序**。
"过去的全量记忆绝大多数用不上" ⇒ 不删正文，但**默认只按范围取需要的**。

索引位置
  `memory` → `memory/index/YYYY-MM.json`（月片，天然有界）
  其他区   → `<区>/index.json`

用法（一般经工作区薄壳 `scratch/memory-tooling/memory_query.py` 调用）
  --rebuild [--zone memory|all] [--month YYYY-MM]  扫磁盘重建/刷新（**合并**，保留人工字段）
  --check [--format json]                          索引 ↔ 磁盘 双向一致性（体检调它）
  --since D --until D --tag T --status S --zone Z --grep RE [--fulltext] --stale [N] --limit N
  --format paths|table|json                        默认 paths（agent 直接拿去读命中文件）
  --set-status S --path P [--add-tag T]            改索引里的元数据（**不动正文**）
退出码：0 正常 / `--check` 一致；1 `--check` 不一致；2 用法错。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import load_config, resolve_root, strip_root_arg  # noqa: E402

INDEX_VERSION = 1
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}
NOT_NOTES = {"README.md", "settings.md"}
STATUSES = ("open", "absorbed", "archived", "dropped")
META_FROM_CONTENT = ("tags", "status", "absorbed_into")
HUMAN_FIELDS = ("desc", "refs", "date", "title")
DEFAULT_ZONES = ["memory", "handbook", "exchange", "scratch", "projects", "archive", "trash"]
DATE_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MAX_TEXT_BYTES = 2 * 1024 * 1024


# ------------------------------------------------------------------ 配置 / 路径

def index_zones(cfg: dict) -> list[str]:
    z = (cfg.get("index") or {}).get("zones")
    if isinstance(z, list) and [x for x in z if str(x).strip()]:
        return [str(x).strip() for x in z if str(x).strip()]
    return list(DEFAULT_ZONES)


def index_file(root: Path, zone: str, month: str | None = None) -> Path:
    return root / "memory" / "index" / f"{month}.json" if zone == "memory" \
        else root / zone / "index.json"


def load_index(p: Path) -> dict:
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(d, dict) and isinstance(d.get("entries"), list):
            return d
    except (OSError, json.JSONDecodeError):
        pass
    return {"version": INDEX_VERSION, "entries": []}


def write_index(p: Path, zone: str, month: str | None, entries: list[dict]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "version": INDEX_VERSION,
        "zone": zone,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "note": "机器台账：由 memory_query.py --rebuild 生成。人工字段（desc/refs/tags/status）在重建时保留。",
    }
    if month:
        data["shard"] = month
    data["entries"] = sorted(entries, key=lambda e: (str(e.get("date", "")), str(e.get("path", ""))), reverse=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


# ------------------------------------------------------------------ 扫描 → 条目

def _sha256(p: Path) -> str:
    try:
        h = hashlib.sha256()
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return ""


def _mtime(p: Path) -> str:
    try:
        return datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="seconds")
    except OSError:
        return ""


def _md_entry(root: Path, p: Path, zone: str) -> dict:
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    rel = p.relative_to(root).as_posix()
    m = re.match(r"(?:memory/)?(\d{4}-\d{2}-\d{2})/", rel)
    d = m.group(1) if m else (datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d") if p.exists() else "")
    tm = re.search(r"^#\s+(.+)$", text, re.M)
    title = tm.group(1).strip() if tm else p.stem
    is_meta = re.compile(r"^(tags|标签|status|状态|absorbed-into|已吸收)\s*[:：]")
    summary = ""
    for line in text.splitlines()[:30]:
        s = line.strip().lstrip(">").strip()
        s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)      # 链接留标签
        s = s.replace("**", "").replace("`", "").strip()
        if not s or s.startswith(("#", "|", "```")) or is_meta.match(s):
            continue
        summary = s[:160]
        break
    tags = []
    tag_m = re.search(r"^>?\s*(?:tags|标签)\s*[:：]\s*(.+)$", text, re.M)
    if tag_m:
        tags = [t.strip() for t in re.split(r"[,，、]", tag_m.group(1)) if t.strip()]
    st = re.search(r"^>?\s*(?:status|状态)\s*[:：]\s*([A-Za-z_]+)", text, re.M)
    status = (st.group(1).strip().lower() if st else "open")
    if status not in STATUSES:
        status = "open"
    ab = re.search(r"^>?\s*(?:absorbed-into|已吸收)\s*[:：]\s*(.+)$", text, re.M)
    absorbed = [t.strip() for t in re.split(r"[,，、]", ab.group(1)) if t.strip()] if ab else []
    return {
        "path": rel, "zone": zone, "kind": "note", "date": d,
        "title": title, "summary": summary, "tags": tags, "status": status,
        "absorbed_into": absorbed, "lines": len(text.splitlines()),
        "sha256": _sha256(p), "mtime": _mtime(p), "desc": "", "refs": "",
    }


def _item_entry(root: Path, p: Path, zone: str, kind: str = "item") -> dict:
    return {
        "path": p.relative_to(root).as_posix(), "zone": zone, "kind": kind,
        "date": datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d") if p.exists() else "",
        "title": p.name, "summary": "", "tags": [], "status": "open",
        "absorbed_into": [], "lines": 0, "sha256": "", "mtime": _mtime(p), "desc": "", "refs": "",
    }


def scan_zone(root: Path, zone: str) -> list[dict]:
    """磁盘上该区**当前应有**的条目（memory = 笔记；其他 = 第一层条目；archive = 快照目录）。"""
    base = root / zone
    out: list[dict] = []
    if not base.is_dir():
        return out
    if zone == "memory":
        for p in sorted(base.rglob("*.md")):
            rel = p.relative_to(root).as_posix()
            if p.name in NOT_NOTES and p.parent == base:
                continue
            if rel.startswith("memory/index/") or any(part in SKIP_DIRS for part in p.parts):
                continue
            out.append(_md_entry(root, p, zone))
        return out
    if zone == "archive":                       # <种类>/<快照日期>/
        for kd in sorted(d for d in base.iterdir() if d.is_dir() and not d.name.startswith((".", "_"))):
            for snap in sorted(d for d in kd.iterdir() if d.is_dir() and not d.name.startswith((".", "_"))):
                out.append(_item_entry(root, snap, zone, "snapshot"))
        return out
    for d in sorted(x for x in base.iterdir() if x.is_dir() and not x.name.startswith((".", "_"))):
        out.append(_item_entry(root, d, zone, "item"))
    if zone == "handbook":                      # 条目就是第一层的 md
        for f in sorted(x for x in base.iterdir()
                        if x.is_file() and x.suffix == ".md" and x.name not in NOT_NOTES):
            out.append(_md_entry(root, f, zone))
    return out


def _merge(scan: list[dict], old: list[dict]) -> tuple[list[dict], int, int]:
    """新扫描为主；**除自动字段外的人工字段一律继承**（正文里显式写的优先）。

    自动字段 = 由磁盘重算的：path/zone/kind/lines/sha256/mtime/summary/title。
    其余（desc、refs、remark、tags、status、absorbed_into、以及将来新增的人工字段）都保留 ——
    所以 `--rebuild` 是**合并**，不会把人工写的内容冲掉。
    """
    auto = ("path", "zone", "kind", "lines", "sha256", "mtime", "summary", "title")
    old_by = {e.get("path"): e for e in old if e.get("path")}
    merged, added = [], 0
    for e in scan:
        prev = old_by.get(e["path"])
        if prev:
            for k in META_FROM_CONTENT:                 # 正文里显式写的优先
                if (not e.get(k) or (k == "status" and e.get(k) == "open")) and prev.get(k):
                    e[k] = prev[k]
            for k, v in prev.items():
                if k in auto or e.get(k):
                    continue
                if k == "date" and e.get("kind") == "note":   # 笔记日期由路径决定
                    continue
                e[k] = v
        else:
            added += 1
        merged.append(e)
    kept = {e["path"] for e in merged}
    removed = len([1 for p_ in old_by if p_ not in kept])
    return merged, added, removed


# ------------------------------------------------------------------ 命令实现

def rebuild(root: Path, cfg: dict, zones: list[str], month: str | None) -> dict:
    rep = {"zones": {}, "added": 0, "removed": 0, "total": 0}
    for zone in zones:
        entries = scan_zone(root, zone)
        if zone == "memory":
            by_month: dict[str, list[dict]] = {}
            for e in entries:
                m = str(e.get("date", ""))[:7] or "unknown"
                by_month.setdefault(m, []).append(e)
            if month:
                by_month = {m: v for m, v in by_month.items() if m == month}
            for m, es in sorted(by_month.items()):
                fp = index_file(root, zone, m)
                merged, added, removed = _merge(es, load_index(fp).get("entries", []))
                write_index(fp, zone, m, merged)
                rep["zones"][f"memory/{m}"] = {"entries": len(merged), "added": added, "removed": removed}
                rep["added"] += added
                rep["removed"] += removed
                rep["total"] += len(merged)
            if month is None:                       # 整月都没笔记了 → 连月片一起清掉
                d = root / "memory" / "index"
                for fp in sorted(d.glob("*.json")) if d.is_dir() else []:
                    if fp.stem not in by_month:
                        fp.unlink()
                        rep.setdefault("dropped_shards", []).append(fp.name)
        else:
            fp = index_file(root, zone)
            merged, added, removed = _merge(entries, load_index(fp).get("entries", []))
            write_index(fp, zone, None, merged)
            rep["zones"][zone] = {"entries": len(merged), "added": added, "removed": removed}
            rep["added"] += added
            rep["removed"] += removed
            rep["total"] += len(merged)
    return rep


def index_check(root: Path, cfg: dict, zones: list[str] | None = None) -> dict:
    """双向一致性：磁盘上有但索引里没有（missing）/ 索引里有但磁盘上没了（stale）。"""
    zones = zones or index_zones(cfg)
    missing, stale, no_index = [], [], []
    for zone in zones:
        disk = {e["path"] for e in scan_zone(root, zone)}
        if zone == "memory":
            d = root / "memory" / "index"
            files = sorted(d.glob("*.json")) if d.is_dir() else []
            if not files and disk:
                no_index.append("memory")
        else:
            fp = index_file(root, zone)
            files = [fp]
            if disk and not fp.is_file():
                no_index.append(zone)
        idx: set[str] = set()
        for fp in files:
            for e in load_index(fp).get("entries", []):
                if e.get("path"):
                    idx.add(e["path"])
        missing += sorted(disk - idx)
        stale += sorted(idx - disk)
    return {"ok": not (missing or stale or no_index), "missing": missing, "stale": stale, "no_index": no_index}


def _iter_entries(root: Path, cfg: dict, zones: list[str]):
    for zone in zones:
        if zone == "memory":
            d = root / "memory" / "index"
            files = sorted(d.glob("*.json")) if d.is_dir() else []
        else:
            files = [index_file(root, zone)]
        for fp in files:
            for e in load_index(fp).get("entries", []):
                yield fp, e


def query(root: Path, cfg: dict, zones: list[str], a: dict) -> list[dict]:
    hits = []
    want_tag = a.get("tag")
    for fp, e in _iter_entries(root, cfg, zones):
        if a.get("since") and str(e.get("date", "")) < a["since"]:
            continue
        if a.get("until") and str(e.get("date", "")) > a["until"]:
            continue
        if a.get("status") and str(e.get("status")) != a["status"]:
            continue
        if want_tag and want_tag not in (e.get("tags") or []):
            continue
        if a.get("kind") and str(e.get("kind")) != a["kind"]:
            continue
        if a.get("grep"):
            blob = " ".join([str(e.get("path", "")), str(e.get("title", "")), str(e.get("summary", "")),
                             " ".join(e.get("tags") or []), str(e.get("desc", ""))])
            if not re.search(a["grep"], blob, re.I):
                if not a.get("fulltext"):
                    continue
        if a.get("fulltext") and a.get("grep"):
            f = root / str(e.get("path", ""))
            if f.is_file() and f.stat().st_size <= MAX_TEXT_BYTES:
                try:
                    if not re.search(a["grep"], f.read_text(encoding="utf-8", errors="replace"), re.I):
                        continue
                except OSError:
                    continue
        if a.get("stale"):
            # 「该结账了」只针对 memory 的笔记（其他区的条目本来就是在位资产，不是待办）
            if str(e.get("zone")) != "memory" or e.get("kind") != "note":
                continue
            if str(e.get("status")) != "open" or not e.get("date"):
                continue
            try:
                if datetime.now() - datetime.strptime(str(e["date"]), "%Y-%m-%d") <= timedelta(days=a["stale"]):
                    continue
            except ValueError:
                continue
        if a.get("has_file"):
            if not (root / str(e.get("path", ""))).exists():
                continue
        hits.append(e)
    hits.sort(key=lambda e: (str(e.get("date", "")), str(e.get("path", ""))), reverse=True)
    if a.get("limit"):
        hits = hits[: a["limit"]]
    return hits


def set_meta(root: Path, cfg: dict, path: str, status: str | None, add_tag: str | None) -> int:
    changed = 0
    for zone in index_zones(cfg):
        for fp, e in list(_iter_entries(root, cfg, [zone])):
            if e.get("path") != path:
                continue
            if status:
                e["status"] = status
            if add_tag and add_tag not in (e.get("tags") or []):
                e.setdefault("tags", []).append(add_tag)
            data = load_index(fp)
            data["entries"] = [e if x.get("path") == path else x for x in data["entries"]]
            write_index(fp, data.get("zone", zone), data.get("shard"), data["entries"])
            changed += 1
    return changed


# ------------------------------------------------------------------ README 活窗口

LIVE_START = "<!-- index:start 由 memory_query.py --refresh 生成，勿手改 -->"
LIVE_END = "<!-- index:end -->"


def _live_selection(cfg: dict, zone: str, entries: list[dict]) -> tuple[list[dict], int]:
    idx_cfg = cfg.get("index") or {}
    live_days = int(idx_cfg.get("live_days", 7))
    cap = int(idx_cfg.get("live_rows", 12))
    if zone == "memory":
        cutoff = (datetime.now() - timedelta(days=live_days)).strftime("%Y-%m-%d")
        sel = [e for e in entries if str(e.get("date", "")) >= cutoff or str(e.get("status")) == "open"]
    else:
        sel = list(entries)
    sel.sort(key=lambda e: (str(e.get("date", "")), str(e.get("path", ""))), reverse=True)
    return sel[:cap], len(sel)


def _render_block(zone: str, shown: list[dict], total: int) -> str:
    src = "`memory/index/*.json`" if zone == "memory" else f"`{zone}/index.json`"
    lines = [LIVE_START, "", "| 日期 | 条目 | 状态 | 摘要 |", "| --- | --- | --- | --- |"]
    for e in shown:
        base = e.get("summary") or e.get("desc") or ""
        extra = []
        if e.get("desc") and e.get("summary") and e["desc"][:20] not in base:
            extra.append(e["desc"])
        if e.get("refs"):
            extra.append("来源：" + str(e["refs"]))
        if e.get("verified"):
            extra.append("验证：" + str(e["verified"]))
        s = base + ("（" + "；".join(extra) + "）" if extra else "")
        lines.append(f"| {e.get('date', '')} | `{e.get('path', '')}` | {e.get('status', '')} | {s.replace('|', '/')[:110]} |")
    more = f"（窗口外还有 {total - len(shown)} 条）" if total > len(shown) else ""
    lines += [
        "",
        f"> 活窗口 {len(shown)}/{total} 条{more}；**完整台账**在 {src} —— 机器读的数据，不参与 md 行数/断链规则。",
        "> 按范围查：`python3 scratch/memory-tooling/memory_query.py "
        f"--zone {zone} --since 2026-09-01 --grep 关键词`（或 `--tag` / `--status` / `--stale`）",
        LIVE_END,
    ]
    return "\n".join(lines)


def refresh(root: Path, cfg: dict, zones: list[str]) -> dict:
    """把各区 README 里的**活窗口**（有界）重新生成；台账本体在 JSON，不写进 README。"""
    rep: dict = {}
    for zone in zones:
        readme = root / zone / "README.md"
        if not readme.is_file():
            continue
        entries = scan_zone(root, zone)
        shown, total = _live_selection(cfg, zone, entries)
        block = _render_block(zone, shown, total)
        text = readme.read_text(encoding="utf-8")
        if LIVE_START in text and LIVE_END in text:
            text = text.split(LIVE_START)[0] + block + text.split(LIVE_END, 1)[1]
        else:
            text = text.rstrip("\n") + "\n\n## 活窗口（自动生成，别手改）\n\n" + block + "\n"
        readme.write_text(text, encoding="utf-8")
        rep[zone] = {"rows": len(shown), "total": total}
    return rep


# ------------------------------------------------------------------ 删除 / 结账（顺着索引）

def _trash_dest(root: Path, rel: str) -> Path:
    parts = Path(rel).parts
    dest = root / "trash" / parts[0] / Path(*parts[1:])
    i = 2
    while dest.exists():
        dest = dest.with_name(dest.name + f"-{i}")
        i += 1
    return dest


def _protected(rel: str, zones: list[str]) -> str | None:
    p = Path(rel)
    if p.name in NOT_NOTES or rel.startswith("memory/index/") or p.name == "index.json":
        return "受保护（README / settings / 索引）"
    if ".." in p.parts:
        return "路径越界"
    if not any(rel == z or rel.startswith(z + "/") for z in zones):
        return "不在索引区内"
    return None


def delete_entries(root: Path, cfg: dict, paths: list[str], hard: bool = False) -> dict:
    """删条目 **并同步索引**。默认 `mv` 到 `trash/<区>/…`（工作区口径 `mv` 不 `rm`），`--hard` 才真删。

    删除后重建受影响区的索引 ⇒ 索引条目**自动跟着消失**，不会留下"读了才发现文件没了"的死链。
    """
    zones = index_zones(cfg)
    moved, gone, skipped = [], [], []
    for rel in paths:
        rel = str(rel).strip().lstrip("./")
        why = _protected(rel, zones)
        p = root / rel
        if why:
            skipped.append((rel, why))
            continue
        if not p.exists():
            skipped.append((rel, "不存在"))
            continue
        if hard:
            shutil.rmtree(p) if p.is_dir() else p.unlink()
            gone.append(rel)
        else:
            dest = _trash_dest(root, rel)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(p), str(dest))
            moved.append((rel, dest.relative_to(root).as_posix()))
    touched = sorted({Path(r).parts[0] for r in paths} | {"trash"})
    rebuild(root, cfg, [z for z in touched if z in zones], None)
    return {"moved": moved, "hard": gone, "skipped": skipped}


def prune(root: Path, cfg: dict, a: dict) -> dict:
    """按范围批量"结账"。默认**只列不删**（要 `--apply`），默认只动 `kind=note`（不碰目录型条目）。"""
    zones = index_zones(cfg) if a.get("zone") in (None, "all") else [a["zone"]]
    crit = {k: a[k] for k in ("since", "until", "status", "tag", "grep", "stale") if a.get(k)}
    if a.get("before"):
        crit["until"] = a["before"]
    crit["kind"] = a.get("kind") or "note"
    hits: list[str] = []
    for z in zones:
        hits += [e["path"] for e in query(root, cfg, [z], dict(crit))]
    if not a.get("apply"):
        return {"dry_run": True, "paths": hits}
    return dict(dry_run=False, **delete_entries(root, cfg, hits, bool(a.get("hard"))))


def stats(root: Path, cfg: dict, zones: list[str]) -> dict:
    """语料体量：**正文总量才是阅读面**（磁盘占用不是问题）。防止"想记住一切"。"""
    out = {}
    for z in zones:
        es = [e for _, e in _iter_entries(root, cfg, [z])]
        out[z] = {"entries": len(es),
                  "notes": sum(1 for e in es if e.get("kind") == "note"),
                  "lines": sum(int(e.get("lines") or 0) for e in es),
                  "open": sum(1 for e in es if e.get("status") == "open")}
    total = sum(v["lines"] for v in out.values())
    budget = int((cfg.get("index") or {}).get("budget_lines", 6000))
    return {"zones": out, "lines": total, "budget": budget, "ok": total <= budget}


# ------------------------------------------------------------------ CLI

USAGE = __doc__.split("用法")[1] if "用法" in __doc__ else ""


def main() -> int:
    argv = strip_root_arg(sys.argv[1:])
    root = resolve_root(sys.argv[1:])
    cfg = load_config(root) if root.is_dir() else {}
    a: dict = {"mode": "query", "zone": "memory", "format": "paths"}
    i = 0
    while i < len(argv):
        t = argv[i]
        nxt = argv[i + 1] if i + 1 < len(argv) and not argv[i + 1].startswith("--") else None
        if t == "--rebuild":
            a["mode"] = "rebuild"
        elif t == "--check":
            a["mode"] = "check"
        elif t == "--refresh":
            a["mode"] = "refresh"
        elif t == "--delete":
            a["mode"] = "delete"
        elif t == "--prune":
            a["mode"] = "prune"
        elif t == "--stats":
            a["mode"] = "stats"
        elif t == "--before" and nxt:
            a["before"] = nxt; i += 1
        elif t == "--apply":
            a["apply"] = True
        elif t == "--hard":
            a["hard"] = True
        elif t == "--month" and nxt:
            a["month"] = nxt; i += 1
        elif t == "--zone" and nxt:
            a["zone"] = nxt; i += 1
        elif t == "--format" and nxt:
            a["format"] = nxt; i += 1
        elif t == "--since" and nxt:
            a["since"] = nxt; i += 1
        elif t == "--until" and nxt:
            a["until"] = nxt; i += 1
        elif t == "--tag" and nxt:
            a["tag"] = nxt; i += 1
        elif t == "--status" and nxt:
            a["status"] = nxt; i += 1
        elif t == "--kind" and nxt:
            a["kind"] = nxt; i += 1
        elif t == "--grep" and nxt:
            a["grep"] = nxt; i += 1
        elif t == "--fulltext":
            a["fulltext"] = True
        elif t == "--limit" and nxt:
            a["limit"] = int(nxt); i += 1
        elif t == "--has-file":
            a["has_file"] = True
        elif t == "--stale":
            a["stale"] = int(nxt) if nxt else int(cfg.get("limits", {}).get("note_stale_days", 30))
            if nxt:
                i += 1
        elif t == "--path" and nxt:
            a["path"] = nxt
            a.setdefault("paths", []).append(nxt)
            i += 1
        elif t == "--set-status" and nxt:
            a["mode"] = "set"; a["status"] = nxt; i += 1
        elif t == "--add-tag" and nxt:
            a["mode"] = "set"; a["add_tag"] = nxt; i += 1
        elif t in ("-h", "--help"):
            print(__doc__); return 0
        else:
            print(f"未知参数：{t}\n\n{__doc__}", file=sys.stderr); return 2
        i += 1

    if not root.is_dir():
        print(f"工作区根不存在：{root}", file=sys.stderr); return 2
    zones = index_zones(cfg) if a["zone"] in ("all", "any") else [a["zone"]]

    if a["mode"] == "rebuild":
        rep = rebuild(root, cfg, zones, a.get("month"))
        for k, v in rep["zones"].items():
            print(f"  {k}: {v['entries']} 条（+{v['added']} / -{v['removed']}）")
        print(f"合计 {rep['total']} 条；新增 {rep['added']}、移除 {rep['removed']}")
        return 0

    if a["mode"] == "stats":
        rep = stats(root, cfg, zones)
        for z, v in rep["zones"].items():
            print(f"  {z:10s} {v['entries']:4d} 条（笔记 {v['notes']:3d}）  {v['lines']:6d} 行  open {v['open']}")
        print(f"正文合计 {rep['lines']} 行 / 预算 {rep['budget']} 行 —— "
              + ("✅ 在预算内" if rep["ok"] else "⚠️ 超预算，该结账了（`--prune --before <日期> --apply`）"))
        return 0

    if a["mode"] == "delete":
        if not a.get("paths"):
            print("--delete 需要 --path", file=sys.stderr)
            return 2
        rep = delete_entries(root, cfg, a["paths"], bool(a.get("hard")))
        for src, dst in rep["moved"]:
            print(f"  moved → {dst}    （原 {src}；索引已同步）")
        for src in rep["hard"]:
            print(f"  deleted（--hard） {src}")
        for src, why in rep["skipped"]:
            print(f"  跳过 {src}：{why}")
        return 0

    if a["mode"] == "prune":
        rep = prune(root, cfg, a)
        if rep.get("dry_run"):
            for p_ in rep["paths"]:
                print(p_)
            print(f"# 干跑：{len(rep['paths'])} 条符合条件；加 --apply 才 mv 到 trash/（--hard 才真删）",
                  file=sys.stderr)
            return 0
        for src, dst in rep["moved"]:
            print(f"  moved → {dst}    （原 {src}；索引已同步）")
        for src in rep["hard"]:
            print(f"  deleted（--hard） {src}")
        for src, why in rep["skipped"]:
            print(f"  跳过 {src}：{why}")
        return 0

    if a["mode"] == "refresh":
        rep = refresh(root, cfg, zones)
        for k, v in rep.items():
            print(f"  {k}: 活窗口 {v['rows']}/{v['total']} 条")
        return 0

    if a["mode"] == "check":
        rep = index_check(root, cfg, zones)
        if a["format"] == "json":
            print(json.dumps(rep, ensure_ascii=False, indent=2))
        else:
            for k in ("missing", "stale"):
                for p_ in rep[k]:
                    print(f"  {'磁盘有但索引缺' if k == 'missing' else '索引有但磁盘没了'}：{p_}")
            for z in rep["no_index"]:
                print(f"  索引文件不存在：{z}")
            print("索引与磁盘一致" if rep["ok"] else "索引与磁盘不一致（跑 --rebuild）")
        return 0 if rep["ok"] else 1

    if a["mode"] == "set":
        if not a.get("path"):
            print("--set-status/--add-tag 需要 --path", file=sys.stderr); return 2
        n = set_meta(root, cfg, a["path"], a.get("status"), a.get("add_tag"))
        print(f"已更新 {n} 条")
        return 0 if n else 1

    hits = query(root, cfg, zones, a)
    if a["format"] == "json":
        print(json.dumps(hits, ensure_ascii=False, indent=2))
    elif a["format"] == "table":
        print(f"{'date':10s}  {'status':9s}  {'lines':>5s}  path")
        for e in hits:
            print(f"{str(e.get('date','')):10s}  {str(e.get('status','')):9s}  {e.get('lines',0):5d}  {e.get('path','')}")
            if e.get("summary"):
                print(f"{'':10s}  {'':9s}  {'':5s}  ↳ {e['summary']}")
    else:
        for e in hits:
            print(e.get("path", ""))
    if a["format"] != "json":
        print(f"# {len(hits)} 条命中（zone={','.join(zones)}）", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
