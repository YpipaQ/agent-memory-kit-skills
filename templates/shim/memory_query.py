#!/usr/bin/env python3
"""记忆索引检索 / 结账（薄壳）：真正的实现在技能 `agent-memory-kit` 里 —— **单一真源，别在此处改逻辑**。

技能目录怎么找（按顺序）：

1. 环境变量 `MEM_KIT_HOME` 指向技能目录；
2. 本文件里的 `{{KIT}}` 占位符 —— 铺开制度时（`bootstrap.sh`）会被替换成本机实际路径。

**这里不写死任何系统路径。**
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.dirname(os.path.dirname(HERE))
TARGET_NAME = "memory_query.py"

CANDIDATES = [
    os.environ.get("MEM_KIT_HOME"),
    "{{KIT}}",
]
for c in CANDIDATES:
    if not c or "{{" in c:
        continue
    target = os.path.join(c, "scripts", TARGET_NAME)
    if os.path.isfile(target):
        args = sys.argv[1:]
        if "--root" not in args and not any(a.startswith("--root=") for a in args):
            args = ["--root", WS, *args]
        os.execv(sys.executable, [sys.executable, target, *args])
raise SystemExit(
    "找不到 agent-memory-kit：设环境变量 MEM_KIT_HOME=<技能目录> 重试，"
    "或重新跑一次 bootstrap.sh（它会把技能目录填进本文件）"
)
