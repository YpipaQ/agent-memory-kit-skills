#!/usr/bin/env python3
"""示例采集器 —— **参考实现，可直接删/改写**。

约定：模块暴露 `collect(root, cfg) -> list[str]`，返回若干行 markdown（含自己的 `## 标题`），
由 `state_snapshot.py` 插进 `STATE.md`。

写你自己的采集器时守住三条：

1. **只读** —— 采集器不改动被采集的东西（不要顺手"修一下"）。
2. **只用标准库** —— 需要外部 CLI 时先判断它在不在；**不在就如实写一句，不要报错、也不要编数字**。
3. **数字由脚本算** —— 易变数字不手写；算不出来就写"本平台不自动探测"，别填一个看着正常的假值。

登记方式（工作区根 `.memory-kit.toml`）：

    [state]
    collectors = ["scratch/memory-tooling/collectors/你的.py"]

本文件被 `bootstrap.sh` 复制到新工作区的 `scratch/memory-tooling/collectors/example.py`，
**默认不登记**（避免每个新工作区都多一段噪音）——要用就把它改名、登记，或另写一个。
"""
from __future__ import annotations

import os
from pathlib import Path

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}


def _human(n: float) -> str:
    x = float(n)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if x < 1024 or unit == "TiB":
            return f"{x:.0f} {unit}" if unit == "B" else f"{x:.1f} {unit}"
        x /= 1024
    return f"{n} B"


def _dir_bytes(path: Path) -> int:
    total = 0
    for base, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            try:
                total += os.path.getsize(os.path.join(base, f))
            except OSError:
                pass
    return total


def collect(root: Path, cfg: dict) -> list[str]:
    lines = ["## 各区体积（示例采集器）", "", "| 区 | 体积 |", "| --- | --- |"]
    for area in cfg.get("areas", []):
        d = root / str(area)
        if d.is_dir():
            lines.append(f"| `{area}/` | {_human(_dir_bytes(d))} |")
    lines += ["", "> 这是**示例**：改成本工作区真正要盯的数字（库体积/行数/缓存/…），再登记进 `.memory-kit.toml`。"]
    return lines
