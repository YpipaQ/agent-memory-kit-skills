#!/usr/bin/env python3
"""热区形态检查 —— 热文件（AGENTS.md）够不够格"扩上限"，读数与体检**同一把尺子**。

背景（用户口径 2026-10-13）：**早点扩展是好事** —— 不要为了省几行去做重审批。
所以这里只回答"形态"：如果文件已经是条目式的（没有大段叙述），就认为**压缩困难、可以扩**。

判据：
  S 条目化率 = 列表项/表格行 ÷ 非空正文行
  W 续行率   = 既非标题也非条目的行 ÷ 总行数（含空行）
  ⇒ 默认门槛 **S ≥ 50% 且 W ≤ 25%**，两者都过 ⇒ 可扩；W 太高 ⇒ 先合并续行再说。
  行数/字节/S/W 一律由 `_common.hot_shape()` 算（**唯一实现**，防与 doctor 读数漂移）。

用法：
  python3 hot_cap_check.py [--root <工作区>] [--json]

输出：行数/上限/余量、字节/注入预算占比、S/W、结论（四选一）。
退出码：**始终 0** —— 它接在收工流程末尾，只报告，不该把流程卡住。
硬顶：`hot_ceil_lines` 行 且 `hot_ceil_bytes` 字节；到顶只能外移/下沉，不再扩。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True            # 不在工作区里留 __pycache__（要在 import _common 之前）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import hot_shape, human, load_config, resolve_root  # noqa: E402


def main(argv: list[str]) -> int:
    as_json = "--json" in argv
    root = resolve_root(argv)
    cfg = load_config(root)
    lim = cfg["limits"]
    cap = int(lim["max_hot_lines"])
    ceil_lines = int(lim["hot_ceil_lines"])
    ceil_bytes = int(lim["hot_ceil_bytes"])
    budget = int(lim["hot_budget_bytes"]) or 1
    step = int(lim["hot_expand_step"])
    gate_s = float(lim["hot_gate_s"])
    gate_w = float(lim["hot_gate_w"])

    hot = root / "AGENTS.md"
    if not hot.is_file():
        if as_json:
            print(json.dumps({"lines": 0, "cap": cap, "bytes": 0, "batch_pct": 0.0,
                              "S": 0.0, "W": 0.0, "verdict": "AGENTS.md 不存在"}, ensure_ascii=False))
        else:
            print(f"热区形态：AGENTS.md 不存在（{hot}）—— 不判形态")
        return 0

    sh = hot_shape(hot.read_text(encoding="utf-8", errors="replace"))
    n, b, S, W = sh["lines"], sh["bytes"], sh["S"], sh["W"]
    pct = b / budget * 100.0

    if b > ceil_bytes or n > ceil_lines:
        verdict = (f"❌ 超硬顶（{ceil_lines} 行 / {human(ceil_bytes)}）"
                   f"—— 只能外移/下沉，不再扩")
    elif n < cap:
        verdict = f"· 未到上限（余量 {cap - n} 行），无需扩"
    elif W > gate_w:
        verdict = f"⚠️ 先合并续行（W {W:.0f}% > {gate_w:.0f}%），再谈扩"
    elif S >= gate_s:
        new_cap = min(cap + step, ceil_lines)
        verdict = (f"✅ 可扩 {new_cap} 行：条目化 S {S:.0f}% ≥ {gate_s:.0f}%、"
                   f"续行 W {W:.0f}% ≤ {gate_w:.0f}% ⇒ 改 max_hot_lines 为 {new_cap}"
                   f"（一次 +{new_cap - cap}）")
    else:
        verdict = f"⚠️ 条目化 S 只有 {S:.0f}% < {gate_s:.0f}% —— 还有叙述水分，先压"

    if as_json:
        print(json.dumps({"lines": n, "cap": cap, "bytes": b, "batch_pct": round(pct, 1),
                          "S": round(S, 1), "W": round(W, 1),
                          "ceil_lines": ceil_lines, "ceil_bytes": ceil_bytes,
                          "verdict": verdict}, ensure_ascii=False))
        return 0

    print(f"热区形态：{n} 行（上限 {cap}，余量 {cap - n}）/ {b} B"
          f"（注入批次 {budget} B 的 {pct:.1f}%）")
    print(f"          条目化 S {S:.0f}%（门槛 ≥{gate_s:.0f}%）｜续行 W {W:.0f}%（门槛 ≤{gate_w:.0f}%）")
    print(f"结论：{verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
