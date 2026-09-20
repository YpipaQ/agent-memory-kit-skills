#!/usr/bin/env python3
"""预设采集器：DSH 模型路由（agent 默认模型 + subagent 白名单）。

从 `~/.dsh/settings.yaml` 读，纯文本解析（不引入 yaml 依赖）。
白名单是**会话开始时冻结**的，改了要新开对话才生效 —— 这段存在 STATE.md 就是为了让
「为什么子代理路由被拒」有据可查。

挂载方式（`.memory-kit.toml`）：

    [state]
    collectors = ["scratch/memory-tooling/collectors/dsh_routes.py"]
"""
from __future__ import annotations

import os
import re
from pathlib import Path

SETTINGS = Path(os.environ.get("DSH_SETTINGS", os.path.expanduser("~/.dsh/settings.yaml")))


def collect(root: Path, cfg: dict) -> list[str]:
    L = ["## DSH 路由（来自 `~/.dsh/settings.yaml`，热重载，改完新开对话生效）", ""]
    try:
        text = SETTINGS.read_text(encoding="utf-8")
    except OSError:
        return L + ["（读不到 settings.yaml）"]
    m = re.search(r"allowedModels:\s*\n(.*?)(?=\n[A-Za-z#])", text, re.S)
    models = re.findall(r"-\s*provider:\s*(\S+)\s*\n\s*model:\s*(\S+)", m.group(1) if m else "")
    m2 = re.search(r"^agent-default-model:\s*\n((?:\s+\S+:.*\n?)+)", text, re.M)
    if m2:
        fields = dict(re.findall(r"(\S+):\s*(\S+)", m2.group(1)))
        route = f"{fields.get('provider', '?')}/{fields.get('model', '?')}"
        effort = fields.get("reasoningEffort")
        L.append(f"- `agent-default-model`：`{route}（reasoningEffort: {effort}）`" if effort
                 else f"- `agent-default-model`：`{route}`")
    if models:
        L.append("- subagent 白名单：")
        L += [f"  - `{p}/{m_}`" for p, m_ in models]
    else:
        L.append("- subagent 白名单：读取失败（手工确认 settings.yaml）")
    return L
