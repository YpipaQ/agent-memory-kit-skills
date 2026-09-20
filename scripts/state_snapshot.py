#!/usr/bin/env python3
"""生成工作区根目录 `STATE.md` —— 「当前数字」的单一真源。

所有**易变数字**（体积/行数/缓存/磁盘/设备/白名单/版本）都由本脚本采集，
不要手写进 AGENTS.md 或冷记忆；AGENTS.md 只留不变量与指针。

用法：
  python3 state_snapshot.py                 # 写入 <root>/STATE.md
  python3 state_snapshot.py --print         # 只打印，不写
  python3 state_snapshot.py --check         # 只判断 STATE.md 是否过期（退出码 1 = 该重生成）
  python3 state_snapshot.py --root /path/ws # 指定工作区

项目特定部分靠 `<root>/.memory-kit.toml` 的 `[state] collectors` 挂载：
每个采集器是一个 `.py`，暴露 `collect(root: Path, cfg: dict) -> list[str]`，返回 markdown 行。
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True            # 不在工作区里留 __pycache__（要在 import _common 之前）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (  # noqa: E402
    config_path, dir_bytes, human, kit_version, load_collectors, load_config,
    resolve_root, run, strip_root_arg, subdirs,
)


def disk_state(root: Path) -> str:
    """工作区所在分区的可用空间。

    用标准库探测（Linux/macOS/Windows 行为一致），**不调用 df** —— `df -h /` 在 Windows/GitBash 下
    指向 MSYS 根，会输出"看着正常、其实是错的"数字（脚本不崩，最容易骗过人）。
    """
    anchor = root.anchor or os.sep
    try:
        u = shutil.disk_usage(anchor)
    except OSError:
        return f"探测不到（{anchor} 不可用）"
    used_pct = round((u.total - u.free) / u.total * 100) if u.total else 0
    return f"{human(u.free)} 可用 / {human(u.total)} 总（已用 {used_pct}%）"


def usb_state() -> list[str] | None:
    """可移动 / 非系统存储设备。**按平台探测；探不了返回 None**，由调用方如实说明，绝不猜。

    Linux 用 `lsblk --json`（没有这个命令也算探不了）；Windows 枚举盘符；macOS 暂不自动探测。
    """
    if sys.platform.startswith("linux"):
        return _lsblk_devices()
    if sys.platform == "win32":
        listdrives = getattr(os, "listdrives", None)       # Python ≥ 3.12
        if listdrives is None:
            return None
        hits = []
        for drive in listdrives():
            if drive.upper().startswith("C:"):
                continue
            try:
                u = shutil.disk_usage(drive)
            except OSError:
                continue
            hits.append(f"{drive} 可用 {human(u.free)} / 总 {human(u.total)}")
        return hits
    return None


def _lsblk_devices() -> list[str] | None:
    """Linux 专用：列出非系统块设备。命令不存在或解析失败 → None（不猜）。"""
    if not shutil.which("lsblk"):
        return None
    try:
        devices = json.loads(run(["lsblk", "--json", "-o",
                                  "NAME,SIZE,FSTYPE,LABEL,MOUNTPOINTS,TYPE"]))["blockdevices"]
    except Exception:
        return None
    skip = {"sda", "sda1", "sr0"}
    hits = []
    for dev in devices:
        name = dev.get("name", "")
        if name in skip or name.startswith("loop"):
            continue
        parts = [(name, dev)] + [(c.get("name", ""), c) for c in dev.get("children", []) or []]
        for pname, p in parts:
            if pname in skip:
                continue
            mount = next((m for m in (p.get("mountpoints") or []) if m), "")
            hits.append(" ".join(x for x in (
                f"/dev/{pname}",
                (p.get("label") or "").strip() or None,
                (p.get("size") or "").strip() or None,
                (p.get("fstype") or "").strip() or None,
                f"已挂载 {mount}" if mount else "未挂载",
            ) if x))
    return hits


def section_archive(root: Path, areas: list[str]) -> list[str]:
    if "archive" not in areas:
        return []
    L = ["## 留档（archive）", ""]
    subs = subdirs(root / "archive")
    if subs:
        L += ["| 目录 | 体积 | 文件数 |", "| --- | --- | --- |"]
        for d in subs:
            p = root / "archive" / d
            n = sum(len(fs) for _b, _d, fs in os.walk(p))
            L.append(f"| `{d}` | {human(dir_bytes(p))} | {n} |")
    else:
        L.append("（暂无归档）")
    L += ["", "外部副本状态见 [`archive/README.md`](archive/README.md)（手工维护，因为涉及物理介质）。"]
    return L


def section_machine(root: Path) -> list[str]:
    usb = usb_state()
    if usb is None:
        usb_line = "本平台不自动探测（Linux 用 `lsblk`、Windows 按盘符；其它平台请手工确认）"
    else:
        usb_line = "；".join(usb) if usb else "未接入"
    return [
        "## 机器资源", "",
        f"- 工作区所在分区：`{disk_state(root)}`",
        f"- USB / 可移动设备：{usb_line}",
    ]


def section_tools(cfg: dict) -> list[str]:
    tf = {}
    for f in ("python3", "node", "git"):
        out = run([f, "--version"])
        tf[f] = out.replace("Python ", "").strip()
    L = ["## 工具版本", ""]
    for t in cfg["state"].get("tools", []) or []:
        ver = run([t, "--version"]) or run([t, "version"])
        L.append(f"- `{t}`：{ver.splitlines()[0] if ver else '未知'}")
    L += [f"- `python3`：{tf.get('python3') or '未知'}",
          f"- `node`：{tf.get('node') or '未安装'}",
          f"- `git`：{tf.get('git') or '未安装'}"]
    return L


def build(root: Path, cfg: dict) -> str:
    now = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M %z")
    L = ["# 工作区当前状态（STATE）", "",
         "> ⚙️ **本文件由脚本生成，请勿手改** —— 改了会在下次生成时被覆盖。",
         "> 重新生成：`python3 scratch/memory-tooling/state_snapshot.py`",
         "> 规则与不变量在 [`AGENTS.md`](AGENTS.md)；过程与结论在 [`memory/`](memory/README.md)。",
         f"> 生成时间：**{now}**　引擎：agent-memory-kit v{kit_version()}", ""]
    for path, mod in load_collectors(root, cfg):
        name = Path(path).name
        if mod is None:
            L += [f"## （采集器缺失：{name}）", "", "配置里的路径不存在，STATE 少一段。", ""]
            continue
        if isinstance(mod, Exception):
            L += [f"## （采集器出错：{name}）", "", f"`{type(mod).__name__}: {mod}`", ""]
            continue
        try:
            lines = mod.collect(root, cfg) or []
        except Exception as exc:
            lines = [f"## （采集器出错：{name}）", "", f"`{type(exc).__name__}: {exc}`"]
        if lines:
            L += list(lines)
            L.append("")
    for sec in (section_archive(root, list(cfg["areas"])), section_machine(root), section_tools(cfg)):
        if sec:
            L += list(sec)
            L.append("")
    return "\n".join(L) + "\n"


def check(root: Path, cfg: dict) -> int:
    out = root / "STATE.md"
    if not out.is_file():
        print("STATE.md 不存在，需要生成")
        return 1
    deps = [Path(d).expanduser() if str(d).startswith(("~", "/")) else (root / d)
            for d in cfg["state"].get("deps", [])]
    stale = [os.path.basename(str(f)) for f in deps
             if f.is_file() and f.stat().st_mtime > out.stat().st_mtime]
    if stale:
        print("STATE.md 比这些数据源旧，该重生成：" + ", ".join(stale))
        return 1
    age_days = (datetime.now() - datetime.fromtimestamp(out.stat().st_mtime)).days
    if age_days > cfg["limits"]["state_max_age_days"]:
        print(f"STATE.md 已 {age_days} 天未更新")
        return 1
    print("STATE.md 新鲜")
    return 0


def main() -> int:
    argv = strip_root_arg(sys.argv[1:])
    root = resolve_root(sys.argv[1:])
    cfg = load_config(root)
    if "--check" in argv:
        return check(root, cfg)
    content = build(root, cfg)
    if "--print" in argv:
        print(content, end="")
        return 0
    out = root / "STATE.md"
    out.write_text(content, encoding="utf-8")
    print(f"已写入 {out}（{len(content.splitlines())} 行）")
    if not cfg["_config_present"]:
        print(f"提示：{config_path(root).name} 不存在，用的是内置默认值（无项目采集器）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
