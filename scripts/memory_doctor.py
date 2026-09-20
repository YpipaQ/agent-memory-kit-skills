#!/usr/bin/env python3
"""记忆体检：断链 / 索引 / 体量 / 结论前置 / 敏感串 / 状态新鲜度 / 交流协议 / 命名。

用法：
  python3 memory_doctor.py                     # 体检当前工作区（自动向上找根）
  python3 memory_doctor.py --root /path/ws     # 指定工作区
  python3 memory_doctor.py --only secrets      # 只跑某几项（逗号分隔）
  python3 memory_doctor.py --list              # 列出可单独运行的项

退出码：0 = 无阻断问题；1 = 有 ❌；用法错 = 2。
⚠️ 只是提醒，❌ 必须修。阈值与豁免都在 `<root>/.memory-kit.toml`，本脚本不含项目特定值。
"""
from __future__ import annotations

import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.dont_write_bytecode = True            # 不在工作区里留 __pycache__（要在 import _common 之前）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (  # noqa: E402
    Report, config_path, kit_version, load_config, resolve_root, strip_root_arg,
)

SECRET_PATTERNS = [
    (r"\b[0-9a-f]{32}\.[A-Za-z0-9_\-]{16,}\b", "疑似 API Key（hex32.alnum，Ollama 风格）"),
    (r"\bsk-[A-Za-z0-9_\-]{16,}\b", "疑似 OpenAI 风格 Key"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "私钥"),
    (r"\bAKIA[0-9A-Z]{16}\b", "AWS Access Key ID"),
    (r"\b(?:ghp|gho|ghu|ghs|github_pat)_[A-Za-z0-9_]{20,}\b", "GitHub Token"),
    (r"\beyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b", "疑似 JWT"),
]
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}
SKIP_EXT = {".parquet", ".duckdb", ".png", ".jpg", ".jpeg", ".webp", ".gif",
            ".zip", ".gz", ".xz", ".pyc", ".pdf"}
EXCHANGE_STATUS = {"pending", "answered", "verified", "absorbed", "abandoned"}
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
DATE_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# 所有检查项（名字用于 --only）
CHECKS = ("config", "links", "placeholders", "areas", "index", "sizes", "tldr", "secrets",
          "state", "exchange", "handbook", "naming")


class Ctx:
    def __init__(self, root: Path, cfg: dict) -> None:
        self.root = root
        self.cfg = cfg
        self.limits = cfg["limits"]
        self.areas: list[str] = list(cfg["areas"])

    def area(self, name: str) -> Path:
        return self.root / name

    def md_files(self) -> list[Path]:
        out = []
        for base, dirs, files in os.walk(self.root):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for f in files:
                if Path(f).suffix.lower() in SKIP_EXT:
                    continue
                if f.endswith(".md"):
                    out.append(Path(base) / f)
        return out

    def all_files(self) -> list[Path]:
        for base, dirs, files in os.walk(self.root):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for f in files:
                p = Path(base) / f
                if p.suffix.lower() in SKIP_EXT:
                    continue
                yield p

    def rel(self, p: Path) -> str:
        try:
            return str(p.relative_to(self.root))
        except ValueError:
            return str(p)

    def area_subdirs(self, *parts: str) -> list[str]:
        try:
            base = self.root.joinpath(*parts)
            return sorted(d for d in os.listdir(base)
                          if (base / d).is_dir() and not d.startswith("_"))
        except OSError:
            return []


# ---------------------------------------------------------------- 各项检查

def check_config(c: Ctx, r: Report) -> None:
    if c.cfg["_config_present"]:
        r.ok(f"配置文件在：{c.rel(Path(c.cfg['_config_path']))}")
    else:
        r.warn_(f"没有 {config_path(c.root).name} —— 用的是内置默认值（区域/阈值/敏感串豁免/STATE 采集器都无法按项目调）")


def check_links(c: Ctx, r: Report) -> None:
    mds = c.md_files()
    broken, placeholder = [], 0
    for p in mds:
        text = p.read_text(encoding="utf-8", errors="replace")
        for target in LINK_RE.findall(text):
            if target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            clean = target.split("#", 1)[0]
            if not clean or clean.startswith("~"):
                continue
            if "<" in clean or ">" in clean:      # 模板占位还没填：算提醒，不算断链
                placeholder += 1
                continue
            resolved = os.path.normpath(os.path.join(os.path.dirname(p), clean))
            if not os.path.exists(resolved):
                broken.append(f"{c.rel(p)} → {target}")
    for b in broken:
        r.bad_(f"断链：{b}")
    if not broken:
        r.ok(f"相对链接全部有效（{len(mds)} 个 md）")
    if placeholder:
        r.warn_(f"有 {placeholder} 条链接还是 <占位符>（模板没填完）")


def check_placeholders(c: Ctx, r: Report) -> None:
    """热记忆里没填完的占位。

    模板铺完最容易漏的一步就是「填定位」。不查的话，新工作区会以 ❌0/⚠0 通过，
    照"全绿=铺好了"判定就会把一个没填说明的工作区当成完成态（这是抽测发现的缺口）。
    """
    hot = c.root / "AGENTS.md"
    if not hot.is_file():
        return
    text = hot.read_text(encoding="utf-8", errors="replace")
    hits = [ln.strip() for ln in text.splitlines() if "{{" in ln or "待填" in ln]
    if hits:
        r.warn_(f"AGENTS.md 还有 {len(hits)} 处没填的占位（如：{hits[0][:44]}）—— 铺完制度别忘了补定位")
    else:
        r.ok("AGENTS.md 没有残留占位")


def check_areas(c: Ctx, r: Report) -> None:
    missing = [a for a in c.areas if not (c.area(a) / "README.md").is_file()]
    for a in missing:
        r.bad_(f"{a}/README.md 缺失（每个区都要有规则说明）")
    if not missing:
        r.ok(f"{len(c.areas)} 个区的 README 都在（{'、'.join(c.areas)}）")
    settings = c.area("memory") / "settings.md"
    if not settings.is_file():
        r.bad_("memory/settings.md 缺失（环境事实的唯一出处）")
    else:
        r.ok("memory/settings.md 在")


def check_index(c: Ctx, r: Report) -> None:
    index = c.area("memory") / "README.md"
    if not index.is_file():
        r.bad_("缺 memory/README.md")
        return
    text = index.read_text(encoding="utf-8")
    mem = c.area("memory")
    notes = [c.rel(p) for p in c.md_files()
             if str(p).startswith(str(mem)) and p.name not in {"README.md", "settings.md"}]
    missing = [n for n in sorted(notes) if Path(n).name not in text]
    for m in missing:
        r.bad_(f"笔记没进索引：{m}")
    if not missing:
        r.ok(f"memory 笔记全部在索引里（{len(notes)} 篇）")
    if "settings.md" not in text:
        r.bad_("memory/README.md 没有引用 settings.md（环境事实的出处要在分工表里可见）")
    indexed = re.findall(r"\]\((20\d\d-\d\d-\d\d/[^)]+\.md)\)", text)
    dangling = [i for i in indexed if not (mem / i).is_file()]
    for d in dangling:
        r.bad_(f"索引指向不存在的笔记：{d}")
    if not dangling and indexed:
        r.ok(f"索引指向的文件都存在（{len(indexed)} 条）")


def check_sizes(c: Ctx, r: Report) -> None:
    lim = c.limits
    hot = c.root / "AGENTS.md"
    if hot.is_file():
        n = len(hot.read_text(encoding="utf-8").splitlines())
        if n > lim["max_hot_lines"]:
            r.warn_(f"AGENTS.md {n} 行 > {lim['max_hot_lines']} 行上限 —— 事实/数字挪进 memory/settings.md 或 STATE.md")
        else:
            r.ok(f"AGENTS.md {n} 行（上限 {lim['max_hot_lines']}）")
    over, due = [], []
    for p in c.md_files():
        if p.name == "README.md":
            continue
        if p.parent == c.area("memory") or str(p.parent).startswith(str(c.area("memory")) + os.sep) \
           or str(p.parent).startswith(str(c.area("handbook"))) or p.parent == c.area("handbook"):
            n = len(p.read_text(encoding="utf-8", errors="replace").splitlines())
            item = f"{c.rel(p)}（{n} 行）"
            if n > lim["max_note_lines"]:
                over.append(item)
            elif lim["compress_trigger_lines"] and n > lim["compress_trigger_lines"]:
                due.append(item)
    hard, trigger, target = lim["max_note_lines"], lim["compress_trigger_lines"], lim["compress_target_lines"]
    for b in over:
        r.bad_(f"超过硬上限 {hard} 行**必须压缩**：{b} —— 删过程史/细节外移，末尾留压缩记录")
    for b in due:
        r.warn_(f"已过触发线 {trigger} 行**该压缩了**：{b} —— 目标 {target} 行；实在压不到才退档，"
                f"且不超硬上限 {hard} 行（下限 {target + 40}），末尾写明压缩记录与原因")
    if not over and not due:
        if trigger:
            r.ok(f"memory/ 与 handbook/ 单篇均 ≤ {trigger} 行"
                 f"（触发线 {trigger} → 目标 {target}；硬上限 {hard}）")
        else:
            r.ok(f"memory/ 与 handbook/ 单篇均 ≤ {hard} 行")


def check_tldr(c: Ctx, r: Report) -> None:
    mem = str(c.area("memory"))
    missing = []
    for p in c.md_files():
        if not str(p).startswith(mem) or p.name == "README.md":
            continue
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        if len(lines) < c.limits["tldr_min_lines"]:
            continue
        head = "\n".join(lines[: c.limits["tldr_head_lines"]])
        if "结论" not in head and "TL;DR" not in head and "TLDR" not in head:
            missing.append(c.rel(p))
    for m in missing:
        r.warn_(f"开头没有结论块（> {c.limits['tldr_min_lines']} 行）：{m}")
    if not missing:
        r.ok("超过阈值的冷记忆都有结论前置")


def check_secrets(c: Ctx, r: Report) -> None:
    from _common import mask
    allow = {os.path.basename(x) for x in c.cfg["secrets"].get("allow_files", [])}
    hits = [f"⚠️ 豁免清单里有不存在的文件：{a}" for a in allow
            if not any(p.name == a for p in c.all_files())]
    for p in c.all_files():
        if p.name in allow:
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for pat, label in SECRET_PATTERNS:
            for m in re.finditer(pat, text):
                hits.append(f"{c.rel(p)}：{label}（{mask(m.group(0))}）")
    for h in hits:
        r.bad_(f"疑似凭据落在文件里：{h}")
    if not hits:
        note = f"；豁免 {'/'.join(sorted(allow))}" if allow else "；无豁免"
        r.ok(f"敏感串扫描通过（{len(SECRET_PATTERNS)} 条规则{note}）")


def check_state(c: Ctx, r: Report) -> None:
    state = c.root / "STATE.md"
    if not state.is_file():
        r.warn_("STATE.md 不存在 —— 跑 python3 scratch/memory-tooling/state_snapshot.py 生成")
        return
    deps = [Path(d).expanduser() if str(d).startswith(("~", "/")) else (c.root / d)
            for d in c.cfg["state"].get("deps", [])]
    stale = [c.rel(f) for f in deps if f.is_file() and f.stat().st_mtime > state.stat().st_mtime]
    age = datetime.now() - datetime.fromtimestamp(state.stat().st_mtime)
    if stale:
        r.warn_(f"STATE.md 比数据源旧（{', '.join(stale)}）—— 重新生成")
    elif age > timedelta(days=c.limits["state_max_age_days"]):
        r.warn_(f"STATE.md 已 {age.days} 天未更新")
    else:
        r.ok("STATE.md 新鲜")


def check_exchange(c: Ctx, r: Report) -> None:
    base = c.area("exchange")
    if not base.is_dir():
        r.bad_("exchange/ 不存在")
        return
    tests = c.area_subdirs("exchange")
    if not tests:
        r.ok("exchange/ 结构就绪（暂无测试）")
        return
    problems = 0
    for t in tests:
        d = base / t
        task, answer = d / "task.md", d / "answer.md"
        if not task.is_file():
            r.bad_(f"exchange/{t} 缺 task.md（出题方必须写测试文档）")
            problems += 1
            continue
        if not answer.is_file():
            r.bad_(f"exchange/{t} 缺 answer.md（协议要求建一个空答复文档）")
            problems += 1
            continue
        text = task.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"^状态:\s*(\S+)", text, re.M)
        if not m:
            r.warn_(f"exchange/{t}/task.md 没有「状态:」行")
        elif m.group(1) not in EXCHANGE_STATUS:
            r.bad_(f"exchange/{t} 状态非法：{m.group(1)}（应为 {'/'.join(sorted(EXCHANGE_STATUS))}）")
            problems += 1
        if len(text.splitlines()) < 8:
            r.warn_(f"exchange/{t}/task.md 太单薄（验收标准可能没写）")
        age = datetime.now() - datetime.fromtimestamp(task.stat().st_mtime)
        if m and m.group(1) == "pending" and age > timedelta(days=c.limits["pending_max_age_days"]):
            r.warn_(f"exchange/{t} 已 pending {age.days} 天（要么催办、要么标 abandoned）")
    if problems == 0:
        r.ok(f"exchange/ 协议检查通过（{len(tests)} 个测试）")


def check_handbook(c: Ctx, r: Report) -> None:
    base = c.area("handbook")
    if not base.is_dir():
        r.bad_("handbook/ 不存在")
        return
    entries = [f for f in os.listdir(base) if f.endswith(".md") and f != "README.md"]
    if not entries:
        r.ok("handbook/ 结构就绪（暂无条目）")
        return
    index = (base / "README.md").read_text(encoding="utf-8")
    missing = [f for f in entries if f not in index]
    for f in missing:
        r.bad_(f"handbook/{f} 没进 handbook/README.md 索引")
    if not missing:
        r.ok(f"handbook/ 条目全部在索引里（{len(entries)} 条）")
    stale = []
    for f in entries:
        text = (base / f).read_text(encoding="utf-8", errors="replace")
        m = re.search(r"最后验证：\*\*(\d{4}-\d{2}-\d{2})\*\*", text)
        if not m:
            stale.append(f"{f}（没写「最后验证」日期）")
            continue
        d = datetime.strptime(m.group(1), "%Y-%m-%d")
        if datetime.now() - d > timedelta(days=c.limits["handbook_max_age_days"]):
            stale.append(f"{f}（最后验证 {m.group(1)}，已超 {c.limits['handbook_max_age_days']} 天）")
    for s_ in stale:
        r.warn_(f"handbook 条目需要复审：{s_}")


def check_naming(c: Ctx, r: Report) -> None:
    """命名规则：memory/ 与 exchange/ 按时间；scratch/、archive/、trash/ 按种类。"""
    bad = []
    for area in ("scratch", "trash"):
        for d in c.area_subdirs(area):
            if re.match(r"^\d{4}-\d{2}-\d{2}", d):
                bad.append(f"{area}/{d} 用了日期前缀（该区按种类命名）")
    for kind in c.area_subdirs("archive"):
        subs = c.area_subdirs("archive", kind)
        if not subs:
            bad.append(f"archive/{kind}/ 下没有快照日期目录")
        for d in subs:
            if not DATE_DIR_RE.match(d):
                bad.append(f"archive/{kind}/{d} 不是日期目录（应为 <种类>/<快照日期>/）")
    for d in c.area_subdirs("memory"):
        if not DATE_DIR_RE.match(d):
            bad.append(f"memory/{d} 不是日期目录（memory 按时间）")
    for d in c.area_subdirs("exchange"):
        if not re.match(r"^\d{4}-\d{2}-\d{2}-", d):
            bad.append(f"exchange/{d} 缺日期前缀（exchange 按时间，形如 YYYY-MM-DD-主题）")
    for b in bad:
        r.bad_(f"命名不符合约定：{b}")
    if not bad:
        r.ok("命名符合约定（memory/exchange 按时间；scratch/archive/trash 按种类）")


RUNNERS = {
    "config": check_config, "links": check_links, "placeholders": check_placeholders,
    "areas": check_areas, "index": check_index,
    "sizes": check_sizes, "tldr": check_tldr, "secrets": check_secrets, "state": check_state,
    "exchange": check_exchange, "handbook": check_handbook, "naming": check_naming,
}


def main() -> int:
    argv = strip_root_arg(sys.argv[1:])
    if "--list" in argv:
        print("可单独运行的检查项：" + "、".join(CHECKS))
        return 0
    only = None
    if "--only" in argv:
        i = argv.index("--only")
        only = [x.strip() for x in argv[i + 1].split(",") if x.strip()] if i + 1 < len(argv) else []
        unknown = [x for x in only if x not in RUNNERS]
        if unknown:
            print(f"未知检查项：{', '.join(unknown)}；可用：{', '.join(CHECKS)}", file=sys.stderr)
            return 2
    root = resolve_root(sys.argv[1:])
    if not root.is_dir():
        print(f"工作区根不存在：{root}", file=sys.stderr)
        return 2
    c = Ctx(root, load_config(root))
    r = Report()
    print(f"记忆体检 @ {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %z')}"
          f"  根目录 {root}  引擎 agent-memory-kit v{kit_version()}")
    for name in (only or CHECKS):
        RUNNERS[name](c, r)
    print("\n".join(r.lines))
    print(f"\n小结：❌ {r.bad} 项，⚠️ {r.warn} 项")
    return 1 if r.bad else 0


if __name__ == "__main__":
    sys.exit(main())
