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
    import tomllib as tomllib          # Python ≥ 3.11 标准库
except ModuleNotFoundError:            # 更老的 Python：用下面的极简回退，仍然零第三方依赖
    tomllib = None


# ---------------------------------------------------------------- 极简 TOML 回退

def _strip_comment(line: str) -> str:
    """去掉注释（引号内的 `#` 不算）。"""
    out, quote = [], ""
    for ch in line:
        if quote:
            out.append(ch)
            if ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
            out.append(ch)
            continue
        if ch == "#":
            break
        out.append(ch)
    return "".join(out)


def _array_balanced(s: str) -> bool:
    depth, quote = 0, ""
    for ch in s:
        if quote:
            if ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
    return depth <= 0


def _split_top(s: str) -> list:
    """按顶层逗号切分（引号内、嵌套数组里的逗号不算）。"""
    parts, cur, depth, quote = [], [], 0, ""
    for ch in s:
        if quote:
            cur.append(ch)
            if ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
            cur.append(ch)
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
            continue
        cur.append(ch)
    tail = "".join(cur).strip()
    if tail:
        parts.append(tail)
    return [p for p in parts if p]


def _scalar(v: str):
    v = v.strip()
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        return [_scalar(x) for x in _split_top(inner)] if inner else []
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        return v


def parse_toml_min(text: str) -> dict:
    """**极简 TOML 子集**：注释 / `[表]` / `key = 字符串·整数·浮点·布尔·数组`（数组可跨行）。

    只覆盖本技能配置用到的语法（见 `.memory-kit.toml`）。有 `tomllib` 时优先用它；
    嵌套表 `[a.b]`、行内表、日期时间等**不支持**（配置里本来也不用）。
    """
    out: dict = {}
    cur: dict = out
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = _strip_comment(lines[i]).strip()
        i += 1
        if not line:
            continue
        if line.startswith("[") and line.endswith("]") and "=" not in line:
            cur = out.setdefault(line[1:-1].strip(), {})
            continue
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        val = val.strip()
        while not _array_balanced(val) and i < len(lines):   # 跨行数组
            val += " " + _strip_comment(lines[i]).strip()
            i += 1
        cur[key.strip()] = _scalar(val)
    return out

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
        "max_area_readme_lines": 120,   # 区 README 只放规则与活窗口，越线 → ⚠️
        "note_stale_days": 30,          # memory 里 open 状态笔记超这么久 → ⚠️「该结账了」
    },
    "secrets": {"allow_files": []},
    # 结构化台账（`memory/index/YYYY-MM.json` 与其他区的 `index.json`）：**数据，不参与 md 行数规则**
    "index": {"zones": ["memory", "handbook", "exchange", "scratch", "projects", "archive", "trash"]},
    # 扫描范围（**默认不漫游整棵树**）：
    #   文档层 = memory/ 递归（无边界）+ 其他各区的**第一层** md + 工作区根目录文件
    #   凭据层 = 各区内所有文件（脚本最可能漏 Key），也可设 "docs" 降级、"." 升级为整棵树
    # include 追加要递归扫的路径（"." = 整棵树）；exclude 在范围内整棵跳过；
    # max_file_bytes 之上的文件不做文本检查（避免把大 dump 当文本读）。
    "scan": {
        "include": [],
        "exclude": [],
        "secrets": "areas",
        "max_file_bytes": 2 * 1024 * 1024,
    },
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
    """读 <root>/.memory-kit.toml，缺文件/缺字段都退回默认值（不抛异常，体检负责提醒）。

    有 `tomllib`（Python ≥ 3.11）就用它；没有就用内置的**极简 TOML 子集**解析 —— 配置只用到
    注释 / `[表]` / `key = 字符串·整数·布尔·数组` 这一小撮语法，所以 **Python ≥ 3.8 也能跑，零第三方依赖**。
    """
    cfg = {k: (dict(v) if isinstance(v, dict) else list(v) if isinstance(v, list) else v)
           for k, v in DEFAULTS.items()}
    p = config_path(root)
    if p.is_file():
        text = p.read_text(encoding="utf-8")
        data = tomllib.loads(text) if tomllib is not None else parse_toml_min(text)
        cfg = _merge(cfg, data)
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
