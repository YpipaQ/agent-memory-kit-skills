#!/usr/bin/env python3
"""预设采集器：同花顺本地行情库 + 下载缓存（供 STATE.md 使用）。

复制到工作区的 `scratch/memory-tooling/collectors/` 后由 `.memory-kit.toml` 挂载：

    [state]
    collectors = ["scratch/memory-tooling/collectors/hithink_market_db.py"]

只读：绝不建库、不改库（`data status` 有建空壳的副作用，所以先判断文件在不在）。
可用环境变量覆盖：`CLI`、`HITHINK_FINANCE_DB_PATH`、`HITHINK_FINANCE_CACHE`。
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

CLI = os.environ.get("CLI", "hithink-finance")
DB = Path(os.environ.get("HITHINK_FINANCE_DB_PATH",
                         os.path.expanduser("~/.local/share/hithink-finance/market.duckdb")))
CACHE = Path(os.environ.get("HITHINK_FINANCE_CACHE", os.path.expanduser("~/.cache/hithink-finance")))


def _run(cmd: list[str], timeout: int = 60) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout.strip()
    except Exception:
        return ""


def _cli_json(args: list[str]):
    try:
        return json.loads(_run([CLI, *args, "--format", "json"]))
    except Exception:
        return None


def _human(n: float) -> str:
    x = float(n)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if x < 1024 or unit == "TiB":
            return f"{x:.0f} {unit}" if unit == "B" else f"{x:.1f} {unit}"
        x /= 1024
    return f"{n} B"


def _db_section() -> list[str]:
    L = ["## 本地行情库", ""]
    if not DB.is_file():
        return L + ["**未初始化**（库文件不存在；`data status` 会创建空壳，别拿它探路）。"]
    st = {"bytes": DB.stat().st_size,
          "mtime": datetime.fromtimestamp(DB.stat().st_mtime).strftime("%Y-%m-%d %H:%M")}
    status = _cli_json(["data", "status"])
    if status and status.get("ok"):
        st["schema_version"] = status["data"].get("version")
    for key, sql in (
        ("rows", "SELECT count(*) AS v FROM raw_kline_daily"),
        ("range", "SELECT min(date)::VARCHAR || ' → ' || max(date)::VARCHAR AS v FROM raw_kline_daily"),
        ("symbols", "SELECT count(DISTINCT thscode) AS v FROM raw_kline_daily"),
        ("events", "SELECT count(*) AS v FROM raw_adjustment_events"),
    ):
        r = _cli_json(["db", "query", "--sql", sql])
        if r and r.get("ok") and r["data"]:
            st[key] = str(r["data"][0].get("v"))
    L += ["| 项 | 值 |", "| --- | --- |", f"| 库文件 | `{DB}` |",
          f"| 体积 | {_human(st['bytes'])}（{st['bytes']} 字节，修改于 {st['mtime']}） |"]
    if "schema_version" in st:
        L.append(f"| schema 版本 | {st['schema_version']} |")
    if "rows" in st:
        L.append(f"| 日K 行数 | {st['rows']}（{st.get('symbols')} 只，{st.get('range')}） |")
    if "events" in st:
        L.append(f"| 复权事件行数 | {st['events']} |")
    return L


def _cache_section() -> list[str]:
    L = ["## 下载缓存（可 `data clean --cache`，但清掉后就不能零下载修复）", ""]
    total = 0
    files = []
    if CACHE.is_dir():
        for f in sorted(CACHE.iterdir()):
            if f.is_file():
                total += f.stat().st_size
                files.append(f)
    L.append(f"- `{CACHE}`：{_human(total)}")
    for f in files:
        L.append(f"  - `{f.name}` {_human(f.stat().st_size)}")
    return L


def collect(root: Path, cfg: dict) -> list[str]:
    return _db_section() + [""] + _cache_section()
