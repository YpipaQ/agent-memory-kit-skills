#!/usr/bin/env python3
"""agent-memory-kit 公共件：工作区根定位 / 配置读取 / 小工具 / 体检报告器。

被 `memory_doctor.py` 与 `state_snapshot.py` 复用；只用标准库（Python ≥ 3.11，需要 tomllib）。

设计要点：**技能本身不知道任何具体工作区**。所有项目差异都从 `<root>/.memory-kit.toml` 读，
没有配置文件就用内置默认值，所以同一套脚本能直接搬到新工作区。
"""
from __future__ import annotations

import os
import sys

# 工作区不是 Python 工程：不要在别人的目录里留 __pycache__（采集器 import 也走这里）
sys.dont_write_bytecode = True

from datetime import datetime
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    tomllib = None

KIT_NAME = "agent-memory-kit"
CONFIG_NAME = ".memory-kit.toml"
KIT_DIR = Path(__file__).resolve().parent.parent

DEFAULT_AREAS = ("memory", "handbook", "exchange", "scratch", "archive", "trash")

DEFAULTS: dict = {
    "areas": list(DEFAULT_AREAS),
    "limits": {
        "max_hot_lines": 70,
        "max_note_lines": 200,         # 硬上限：超过判 ❌
        "compress_trigger_lines": 150,  # 单篇过线 → ⚠️「该压缩」（0 = 不设触发线）
        "compress_target_lines": 80,    # 压缩目标行数（提示文案用；退档 = 触发线+50 / 目标+40）
        "tldr_min_lines": 80,
        "tldr_head_lines": 12,
        "state_max_age_days": 7,
        "pending_max_age_days": 3,
        "handbook_max_age_days": 90,
    },
    "secrets": {"allow_files": []},
    "state": {"collectors": [], "deps": [], "tools": []},
}


# ---------------------------------------------------------------- 根定位

def strip_root_arg(argv: list[str]) -> list[str]:
    """从参数表里摘掉 --root/--root=X，返回其余参数。"""
    out, i = [], 0
    while i < len(argv):
        a = argv[i]
        if a == "--root":
            i += 2
            continue
        if a.startswith("--root="):
            i += 1
            continue
        out.append(a)
        i += 1
    return out


def resolve_root(argv: list[str] | None = None) -> Path:
    """按优先级定位工作区根：--root 参数 → MEM_KIT_ROOT → 向上找配置/六区特征 → 当前目录。"""
    argv = list(sys.argv[1:] if argv is None else argv)
    for i, a in enumerate(argv):
        if a == "--root" and i + 1 < len(argv):
            return Path(argv[i + 1]).expanduser().resolve()
        if a.startswith("--root="):
            return Path(a.split("=", 1)[1]).expanduser().resolve()
    env = os.environ.get("MEM_KIT_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    cur = Path.cwd().resolve()
    chain = [cur, *cur.parents]
    for d in chain:                       # 1) 有配置文件的就是根
        if (d / CONFIG_NAME).is_file():
            return d
    for d in chain:                       # 2) 退一步：AGENTS.md + memory/ 同时存在
        if (d / "AGENTS.md").is_file() and (d / "memory").is_dir():
            return d
    return cur


# ---------------------------------------------------------------- 配置

def _merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def config_path(root: Path) -> Path:
    return root / CONFIG_NAME


def load_config(root: Path) -> dict:
    """读 <root>/.memory-kit.toml，缺文件/缺字段都退回默认值（不抛异常，体检负责提醒）。"""
    cfg = {k: (dict(v) if isinstance(v, dict) else list(v) if isinstance(v, list) else v)
           for k, v in DEFAULTS.items()}
    p = config_path(root)
    if p.is_file():
        if tomllib is None:
            raise SystemExit("需要 Python ≥ 3.11（tomllib）来读 .memory-kit.toml")
        with open(p, "rb") as fh:
            cfg = _merge(cfg, tomllib.load(fh))
    cfg["_config_present"] = p.is_file()
    cfg["_config_path"] = str(p)
    return cfg


def kit_version() -> str:
    v = KIT_DIR / "VERSION"
    try:
        return v.read_text(encoding="utf-8").strip()
    except OSError:
        return "?"


# ---------------------------------------------------------------- 小工具

def run(cmd: list[str], timeout: int = 60) -> str:
    import subprocess
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.stdout.strip()
    except Exception:
        return ""


def human(n: float) -> str:
    x = float(n)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if x < 1024 or unit == "TiB":
            return f"{x:.0f} {unit}" if unit == "B" else f"{x:.1f} {unit}"
        x /= 1024
    return f"{n} B"


def dir_bytes(path: Path) -> int:
    total = 0
    for base, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(base, f))
            except OSError:
                pass
    return total


def subdirs(path: Path) -> list[str]:
    try:
        return sorted(d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d)))
    except OSError:
        return []


def files_in(path: Path) -> list[str]:
    try:
        return sorted(f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f)))
    except OSError:
        return []


def mask(s: str) -> str:
    """只留头 6 尾 4，避免完整凭据进日志。"""
    return s[:6] + "…" + s[-4:] if len(s) > 12 else "…"


def mtime_age_days(p: Path) -> float:
    return (datetime.now() - datetime.fromtimestamp(p.stat().st_mtime)).total_seconds() / 86400


# ---------------------------------------------------------------- 采集器

def load_collectors(root: Path, cfg: dict) -> list[tuple[str, object]]:
    """加载配置里 state.collectors 指定的采集器模块；每个模块暴露 collect(root, cfg) -> list[str]。"""
    import importlib.util
    out: list[tuple[str, object]] = []
    for spec_path in cfg.get("state", {}).get("collectors", []) or []:
        p = Path(spec_path).expanduser()
        if not p.is_absolute():
            p = (root / p).resolve()
        if not p.is_file():
            out.append((str(p), None))
            continue
        spec = importlib.util.spec_from_file_location(f"memkit_collector_{p.stem}", p)
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
            out.append((str(p), mod))
        except Exception as exc:  # 采集器坏了不该拖垮 STATE 生成
            out.append((str(p), exc))
    return out


# ---------------------------------------------------------------- 报告器

class Report:
    """体检结果收集器：❌ 阻断、⚠️ 提醒、✅ 通过。"""

    def __init__(self) -> None:
        self.bad = 0
        self.warn = 0
        self.lines: list[str] = []

    def ok(self, msg: str) -> None:
        self.lines.append(f"  ✅ {msg}")

    def warn_(self, msg: str) -> None:
        self.warn += 1
        self.lines.append(f"  ⚠️  {msg}")

    def bad_(self, msg: str) -> None:
        self.bad += 1
        self.lines.append(f"  ❌ {msg}")
