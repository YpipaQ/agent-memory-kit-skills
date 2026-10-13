#!/usr/bin/env python3
"""硬值点名核对 —— 检查压缩/改写后的文件有没有丢掉原文的**不可推导硬值**，并核对"外移"有没有真身。

用法：
  python3 check_hard_values.py <原文件> <新文件> [--externed MAP] [--dump DIR]
  python3 check_hard_values.py <原文件> <新文件> --infer-externed     # 只打印草稿 map，不写盘

输入：
  - <原文件>：压缩/改写**前**的 markdown；<新文件>：待核对的那份
  - `--externed MAP`：侧车表（登记"哪些值外移到了哪"）。条目形如
    `{"value": "<值或正则>", "home": "<真身文件路径>", "why": "<为什么>"}`；
    接受 `{"entries":[...]}` / 裸 list / `{"<值>": {"home":...}}` 三种写法。
  - `--dump DIR`：把两侧硬值集合与本次结论另存到目录（不覆盖正文）
  - `--infer-externed`：用"值在原文件里所在行的 markdown 链接"推断 home，**只打印草稿 map**

输出三类结论（只对"原文有、新文件没有"的值判）：
  - ❌ **真丢失**：没登记外移 —— 必须找回或补登记
  - ✅ **已外移**：登记了，且值确实出现在 `home` 且 `home` 存在
  - ⚠️ **映射失效**：登记了，但 `home` 不存在、或值不在其中（映射过期 / 真身没写）

退出码：1 **iff** 真丢失 > 0；0 = 其余；2 = 用法错。
边界：只做**机械**核对（路径/反引号/版本/带单位数值/哈希/脚本名）；
      语义丢失（口径、⚠️ 坑、结论）机器查不出来，得人眼点名；也**只管"值还在不在"，不管"值还对不对"**。
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True            # 不在工作区里留 __pycache__（要在 import _common 之前）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import FS_PATH_ROOTS  # noqa: E402

# 路径根集合**取自 `_common.FS_PATH_ROOTS`**（与 check_stale_values 同一口径：/opt、/ias、/srv、/root
# 不许被静默漏掉）。其余硬值正则沿用工作区版（首版核对的判据，别自己加花样）。
_PATH_ALT = "|".join(re.escape(r) for r in FS_PATH_ROOTS)
PATTERNS = {
    "路径": r"(?<![\w\u4e00-\u9fff])(?:" + _PATH_ALT + r")/[\w.\-/]+",
    "反引号片段": r"`([^`\n]+)`",
    "版本号": r"\b\d+\.\d+\.\d+\b",
    "带单位数值": r"\b\d+(?:\.\d+)?\s?(?:cm|mm|pt|px|磅|%)\b",
    "哈希": r"\b[0-9a-f]{16,}\b",
    "脚本/文件名": r"(?<![\w/])[\w.\-]+\.(?:py|md|json|sh|conf|docx|pdf|png|txt)\b",
}
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")


def hard_values(text: str) -> set[str]:
    out: set[str] = set()
    for pat in PATTERNS.values():
        for m in re.finditer(pat, text):
            token = (m.group(1) if m.lastindex else m.group(0)).strip().strip("`").strip()
            if token:
                out.add(token)
    return out


def load_map(path: str | None) -> list[dict]:
    """读侧车表；**容忍格式差异**，坏文件/缺文件都退化成空表（并在 stderr 说清楚）。"""
    if not path:
        return []
    p = Path(path).expanduser()
    if not p.is_file():
        print(f"⚠️  映射表不存在：{p}（本次所有缺失都按「未登记外移」处理）", file=sys.stderr)
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"⚠️  映射表读不了：{p}（{e}）", file=sys.stderr)
        return []
    if isinstance(data, dict):
        inner = data.get("entries") or data.get("map") or data.get("externed")
        if isinstance(inner, list):
            data = inner
        else:   # {"<值>": {...}} / {"<值>": "<home>"}
            data = [dict(v, value=k) if isinstance(v, dict) else {"value": k, "home": v}
                    for k, v in data.items()]
    entries: list[dict] = []
    for e in data if isinstance(data, list) else []:
        if not isinstance(e, dict):
            continue
        val = str(e.get("value", "")).strip()
        if val:
            entries.append({"value": val, "home": str(e.get("home", "")).strip(),
                            "why": str(e.get("why", "")).strip()})
    return entries


def match_entry(entries: list[dict], value: str) -> dict | None:
    """先精确匹配，再按正则整体匹配（映射支持字符串与正则）。"""
    for e in entries:
        if e["value"] == value:
            return e
    for e in entries:
        try:
            if re.fullmatch(e["value"], value):
                return e
        except re.error:
            continue
    return None


def _home_text(home: str) -> str | None:
    if not home:
        return None
    p = Path(home).expanduser()
    if not p.is_file():
        return None
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _line_with(text: str, value: str) -> str:
    for line in text.splitlines():
        if value in line:
            return line
    return ""


def infer_home(src_text: str, src_path: Path, value: str) -> str:
    """用"值所在行的 markdown 链接"推断 home（相对链接按原文件所在目录解析）；推不出返回 ""。"""
    line = _line_with(src_text, value)
    for target in LINK_RE.findall(line):
        t = target.split("#", 1)[0].strip()
        if not t or "://" in t or t.startswith(("mailto:", "#")):
            continue
        p = Path(t).expanduser()
        cand = p if p.is_absolute() else (src_path.parent / p)
        try:
            cand = cand.resolve()
        except OSError:
            continue
        if cand.is_file():
            return str(cand)
    return ""


def main(argv: list[str]) -> int:
    positional: list[str] = []
    map_path = dump_dir = None
    infer = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--externed":
            if i + 1 >= len(argv):
                print("用法错：--externed 后面要接侧车表路径", file=sys.stderr)
                return 2
            map_path = argv[i + 1]
            i += 2
        elif a.startswith("--externed="):
            map_path = a.split("=", 1)[1]
            i += 1
        elif a == "--dump":
            if i + 1 >= len(argv):
                print("用法错：--dump 后面要接目录", file=sys.stderr)
                return 2
            dump_dir = argv[i + 1]
            i += 2
        elif a.startswith("--dump="):
            dump_dir = a.split("=", 1)[1]
            i += 1
        elif a == "--infer-externed":
            infer = True
            i += 1
        elif a.startswith("-"):
            print(f"未知参数：{a}", file=sys.stderr)
            return 2
        else:
            positional.append(a)
            i += 1

    if len(positional) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    src, dst = Path(positional[0]).expanduser(), Path(positional[1]).expanduser()
    for p in (src, dst):
        if not p.is_file():
            print(f"文件不存在：{p}", file=sys.stderr)
            return 2
    src_text = src.read_text(encoding="utf-8", errors="replace")
    dst_text = dst.read_text(encoding="utf-8", errors="replace")
    before, after = hard_values(src_text), hard_values(dst_text)
    missing = sorted(before - after)

    if infer:
        draft = [{"value": v, "home": infer_home(src_text, src, v),
                  "why": "<待填：这条值为什么能外移/外移到哪>"} for v in missing]
        print(json.dumps({"note": "草稿：--infer-externed 只打印，不写盘；home 由值所在行的 markdown 链接推断",
                          "entries": draft}, ensure_ascii=False, indent=1))
        print(f"（原文 {len(before)} 项、新文件 {len(after)} 项；待推断 {len(draft)} 项）", file=sys.stderr)
        return 0

    entries = load_map(map_path)
    lost, externed, invalid = [], [], []
    for v in missing:
        e = match_entry(entries, v)
        if e is None:
            lost.append(v)
            continue
        txt = _home_text(e["home"])
        if txt is not None and v in txt:
            externed.append((v, e))
        else:
            invalid.append((v, e))

    if dump_dir:
        out = Path(dump_dir).expanduser()
        try:
            out.mkdir(parents=True, exist_ok=True)
            (out / "hard-values-before.txt").write_text("\n".join(sorted(before)) + "\n", encoding="utf-8")
            (out / "hard-values-after.txt").write_text("\n".join(sorted(after)) + "\n", encoding="utf-8")
            (out / "hard-values-check.json").write_text(json.dumps(
                {"before": len(before), "after": len(after),
                 "lost": lost, "externed": [v for v, _ in externed],
                 "invalid": [{"value": v, "home": e["home"], "why": e["why"]} for v, e in invalid]},
                ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        except OSError as e:
            print(f"⚠️  --dump 写不了：{out}（{e}）", file=sys.stderr)

    print(f"原文硬值 {len(before)} 项；新文件 {len(after)} 项；新增 {len(after - before)} 项；"
          f"缺失 {len(missing)} 项")
    if externed:
        print(f"\n✅ 已外移且有真身 {len(externed)} 项：")
        for v, e in externed:
            print(f"  - {v}  ← {e['home']}")
    if invalid:
        print(f"\n⚠️ 映射失效 {len(invalid)} 项（home 不存在，或值不在其中——登记过期/真身没写）：")
        for v, e in invalid:
            print(f"  - {v}  ← home {e['home'] or '(空)'}  why: {e['why'] or '(未写)'}")
    if lost:
        print(f"\n❌ 真丢失 {len(lost)} 项（新文件没有、也没登记外移）：")
        for v in lost:
            print(f"  - {v}")
        return 1
    if not missing:
        print("\n✅ 无硬值丢失（机械核对）")
    else:
        print("\n✅ 无真丢失（缺失项都已登记外移）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
