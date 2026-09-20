#!/usr/bin/env python3
"""生成 STATE.md（薄壳）：真正的实现在 agent-memory-kit 技能里 —— 单一真源。

备选查找顺序：MEM_KIT_HOME → ~/.dsh/skills/agent-memory-kit → 铺开时记录的本机技能路径。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.dirname(os.path.dirname(HERE))          # scratch/memory-tooling/x.py → 工作区根
TARGET_NAME = "state_snapshot.py"

CANDIDATES = [
    os.environ.get("MEM_KIT_HOME"),
    os.path.expanduser("~/.dsh/skills/agent-memory-kit"),
    "{{KIT}}",
]
for c in CANDIDATES:
    if not c:
        continue
    target = os.path.join(c, "scripts", TARGET_NAME)
    if os.path.isfile(target):
        args = sys.argv[1:]
        if "--root" not in args and not any(a.startswith("--root=") for a in args):
            args = ["--root", WS, *args]
        os.execv(sys.executable, [sys.executable, target, *args])
raise SystemExit("找不到 agent-memory-kit（设 MEM_KIT_HOME 指向技能目录，或确认 ~/.dsh/skills/agent-memory-kit 软链还在）")
