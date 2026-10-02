---
name: agent-memory-kit-skills
description: Workspace memory system for long-running AI collaboration: hot/cold note separation, structured JSON ledger with scoped retrieval, project registration cards, secret-scan gate, and a health check. Use when recording memory, auditing a workspace or project, or bootstrapping a new one. 中文触发：「记一下」「落盘」「整理记忆」「体检一下」「更新 STATE」「这个流程定型了」「多智能体测试」「建个项目」「这个项目发不发布/退役」「按范围查记忆」。EN: "take notes" "workspace memory" "health check" "secret scan" "project card" "bootstrap".
---

# agent-memory-kit-skills — workspace memory system

**One line**: a workspace memory system that keeps long-running AI collaboration from depending on chat history — rules go to hot memory, facts to one settings file, numbers to scripts, process to cold notes, settled procedure to the handbook, tests through the exchange protocol, and anything to discard into `trash/` first.

**一句话**：让"长期与 AI 一起干活的目录"不靠聊天记录活着 —— 规则进热记忆、事实进一份 settings、
数字交给脚本、过程进冷记忆、定型进手册、测试走协议、要扔的先挪进 trash。

## 1. What breaks without this

长期协作的目录坏掉，几乎总是这几种方式；每条规则都对应一种病：

1. **同一件事写在好几处**，改一处忘一处 → 后来的人读到两个版本，不知道哪个算数 ⇒ 药：**事实只写一次**，别处只放链接。
2. **热记忆越写越长**（它每次都要被注入） → 越读越慢、越读越贵 ⇒ 药：只留规则与导航，事实挪 `settings`，数字交脚本。
3. **笔记只进不出**，最后想"记住一切" → 阅读面无限膨胀 ⇒ 药：**台账与散文分开**（见第 4 节）+ **按范围取用**。
4. **索引写在给人读的文档里** → 文档随条目数膨胀，必然撞死行数上限（实测：18 篇/天，5 天撞 150 行）
   ⇒ 药：台账放进**机器读的 JSON**，README 只留规则与**活窗口**。
5. **测试/复核没有分工** → 说不清结论是谁写的、验到哪一层 ⇒ 药：出题作答走 `exchange/` 协议（谁写哪个文件一目了然）。
6. **同一份东西存多处，各自演化** → 三份"都能跑"，谁也不知道哪份算数
   ⇒ 药：**一处真身 ＋ 登记卡**（见第 3 节末），"为了同步而同步"的机制一律退役。

## 2. Three rules to remember

1. **事实只写一次**：同一件事（端点、阈值、当前数字、流程）**只有一个文件**是真源，别处用链接指过去。
2. **到线就压**：单篇默认**到 150 行压到 80 行**；实在压不到才退档（上限 +50 = 200、下限 +40 = 120，
   即老实落在 120~200），末尾留一行「压缩记录：删了什么、去哪了、为何到不了 80」。
3. **测试走 `exchange/`**：出题方写 `task.md` 并留一个空的 `answer.md`；作答方**只写 `answer.md`**；
   结论由出题方复核后才写进记忆。目的是**写入范围可查、复盘有据**，不是防谁。

## 3. Where things live

区的清单由工作区根 `.memory-kit.toml` 的 `areas` 决定，默认六区；`projects`、`data` 是常见的加挂区，
模板随技能提供，`bootstrap.sh --areas ...` 可以一并铺开。

| 区 | 放什么 | 判断标准 | 命名 |
| --- | --- | --- | --- |
| `memory/` | 在办的事、试出的结论、失败尝试、待办 | **要读**的叙述 | 按时间：`YYYY-MM-DD/主题.md` |
| `handbook/` | 已定型、实测通过、可照做的流程与参数 | **可照做**的速查 | 按主题：`<主题>.md` |
| `exchange/` | 出题/作答的受控交流（多智能体测试） | **要传**的话 | 按时间：`YYYY-MM-DD-主题/` |
| `scratch/` | 可复跑的脚本、基准、产物（**没确认的复用产物先放这**） | **要跑**的东西 | 按种类：`<种类>/` |
| `projects/`〔加挂〕 | 要开发、会持续维护的项目：**内嵌真身**，或**真身在外、本区只放登记卡** | **要构建**的东西 | 按种类：`<项目>/` |
| `data/`〔加挂〕 | 机器用的大文件：活库、下载缓存、锁 | **机器用**的（可再生、不外发） | 按种类：`<种类>/` |
| `archive/` | 会被滚动窗口挤掉、不可再生的数据快照 | **要留**的数据 | `archive/<种类>/<快照日期>/` |
| `trash/` | 用过且不会再读的产物（`mv` 不 `rm`） | **要扔**的东西 | 按种类：`<种类>/` |

- **先 `scratch/` 后 `projects/`**：新东西默认放 `scratch/`（整区可弃）；**用户确认**要长期维护才迁进
  `projects/`，并改掉所有引用。与 `scratch/` 相反，`projects/` **不能整区删除**。
- 加挂一个区要三样：`templates/areas/<区>/README.md` 模板、`areas` 里加一项、`AGENTS.md` 导航表补一行
  （**等该区真的存在**再加链接，否则体检判断链）。

**三层内容分离**（防漂移的核心）：

| 层 | 文件 | 内容 | 更新方式 |
| --- | --- | --- | --- |
| 热 | `AGENTS.md` | 只有提示词、规则、长期习惯 + 导航表 | 人/AI 手改，越短越好（默认 ≤ 70 行） |
| 半稳定 | `memory/settings.md` | 端点、Key 位置、路径、模型名、口径坑 | 手改 |
| 易变 | `STATE.md` | 体积/行数、缓存、归档、磁盘、设备 | **脚本生成，勿手改** |

项目差异**不写进脚本**，全部写在根目录 `.memory-kit.toml`（区清单、阈值、敏感串豁免、扫描范围、索引、采集器、项目区形态）。

**项目的形态：一处真身 ＋ 登记卡 ＋ 回退副本**（`[projects] mode`）：

- `embedded`（默认）：真身就在 `projects/<名>/`；`card`：真身在工作区外的 `truth_root/<名>/`，
  本区只放一张 ≤40 行的**登记卡**（真身路径／类别／可见性／状态／git／指针，**不放代码、不复制说明**）。
- **判断类的事不写进脚本**：建不建、要不要外发、算不算退役 —— 读 [`references/项目管理.md`](references/项目管理.md)（自然语言的建议，人拍板）。
- 体检只核对**形式**（`cards` 项）：卡在不在、真身路径指不指得到、真身根下有没有漏登记的。

## 4. The ledger is data, the README is rules

**问题**：把"一行一条"的台账写进给人读的 README，README 就是 O(条目数) 增长，早晚撞死行数上限；
而体检又要求"每条都得进索引"——两条规则互相打架。

**做法**：分开两种东西。配套脚本（**参考实现**，可照你自己的 harness 重写）负责：重建台账、校验
"索引 ↔ 磁盘"一致、刷新活窗口、按范围检索（时间/标签/状态/关键词/超期）、看阅读面体量、批量结账 —— 命令见第 7 节。

- **规则 + 活窗口**留在各区 `README.md`：只讲怎么放、怎么查，加一张"近 N 天 + 未结项"的小表（脚本生成，**大小恒定**）。
- **全量台账**放进机器读的结构化文件：`memory/index/YYYY-MM.json`（按月分片）与其他区的 `<区>/index.json` ——
  它是**数据**，不受 md 行数/断链规则约束；涨到几千条也只是几百 KB，**没有人需要全量读它**。
- **正文永远保留**；删除要顺着索引走：默认**先挪进 `trash/`**（`mv` 不 `rm`），要真删才显式说明。

## 5. Day-to-day use

| 场景 | 怎么做 |
| --- | --- |
| **A 给新工作区落地** | `bootstrap.sh` 铺目录与模板 → 补 `AGENTS.md` 定位 → 体检 ❌ 清零 → 生成第一份 `STATE.md` → 出第一道交流测试 |
| **B 日常记录**（做完一段再落盘） | 同类事情改**同一个文件** → `state_snapshot.py` → `memory_query.py --rebuild` → `--refresh` → 体检；**不用**手动往 README 加索引行 |
| **C 多智能体测试** | `new_exchange.sh` 建题 → 作答方只写 `answer.md` → **自己独立复跑关键步骤**（小而短、质量高的值得重复）→ 标 `verified` → 结论进 `memory/`／`handbook/` 并标 `absorbed`；可复用成果**要搬走** |
| **D 阅读面收不住** | `--stats` 看体量 → `--stale` 找超期未结项 → 用不上的 `--prune --before <日期> --apply` 挪进 `trash/`；"过去的大多用不上"≠删光，是**默认不读全部** |
| **E 对外发布／拷介质** | 只跑 `--only secrets` → 逐文件校验（更强就绕过页缓存真读设备）→ 结论写进 `archive/README.md` 的副本表 |

## 6. Privacy red lines

- Key **不进**脚本、日志、命令参数、`STATE.md`、外部副本；打印只留掩码。
- 允许出现敏感串的文件必须**在配置里显式豁免**（默认一个都不豁免）—— 豁免是**要人确认**的决定。
- 用户级凭据文件收紧权限；`git init` 只是本机建库，**推远端前**先处理明文 Key、按可见性分级、
  并**逐提交扫一遍历史**（区间写法会静默漏过）。细节见 [`references/隐私与密钥.md`](references/隐私与密钥.md)。

## 7. Implementation notes

- **只依赖两样大伙都有的东西**：一个 POSIX shell（`bootstrap.sh` 与薄壳）＋ 一个 Python 3（脚本）。
  **不装第三方包**：有 `tomllib`（≥ 3.11）就用，没有就用内置的极简 TOML 子集 ⇒ **Python ≥ 3.8 可用**。
- **不调任何外部程序**（默认 `[state] tools = []`）；平台数字**探不到就如实写一句**，绝不填"看着正常"的假数字。
- **不含系统专有路径**：薄壳认 `MEM_KIT_HOME`，或由 `bootstrap.sh` 把本机技能目录填进占位符 —— 换机器重跑一次即可。
  **Windows 与 Linux 不一样的地方（路径长什么样、有没有某条命令、怎么开命令行）一律用自然语言写清 ＋ 现场探测**，
  不写死专有命令，也不硬编码"必须以斜杠开头"这类只在一边成立的判断。
- **`scripts/` 与 `templates/` 是参考实现**：制度本身是**自然语言**的规则，可以用你 harness 的原生工具重写。

常用命令（技能目录按你的环境替换）：

| 目的 | 命令 |
| --- | --- |
| 体检一个工作区 | `python3 scripts/memory_doctor.py --root <工作区>` |
| 只查敏感串（发布/拷盘前） | `python3 scripts/memory_doctor.py --root <工作区> --only secrets` |
| 只核对项目卡 ↔ 真身 | `python3 scripts/memory_doctor.py --root <工作区> --only cards` |
| 生成易变数字快照 | `python3 scripts/state_snapshot.py --root <工作区>` |
| 记忆索引：重建 / 校验 / 活窗口 / 体量 | `python3 scripts/memory_query.py --root <工作区> [--rebuild\|--check\|--refresh\|--stats]` |
| 按范围检索 / 结账 | `python3 scripts/memory_query.py --root <工作区> [--since D --grep 词 \| --stale 30 \| --delete --path P \| --prune --before D --apply]` |
| 建交流测试目录 | `bash scripts/new_exchange.sh --root <工作区> "YYYY-MM-DD-主题" "说明"` |
| 铺开各区（默认六区，可加挂） | `bash scripts/bootstrap.sh --root <新目录> [--areas memory,...,projects,data] [--collector <采集器.py>] [--name 名字]` |

退出码：体检 `0` 无阻断 / `1` 有 ❌；`--check` 一致 `0` / 不一致 `1`；`new_exchange.sh` `2` 已存在 / `3` 模板缺失 / `4` 目录名不合规。

## 8. Document map

| 需要什么 | 读 |
| --- | --- |
| 区细则、命名、压缩、索引与散文分离、体检各项、配置全字段 | [`references/记忆制度.md`](references/记忆制度.md) |
| 交流协议全文与状态机、复核层次、与任务板的对接 | [`references/交流协议.md`](references/交流协议.md) |
| 密钥卫生、扫描与豁免、外部副本与 git 前置 | [`references/隐私与密钥.md`](references/隐私与密钥.md) |
| 脚本用法、退出码、`--only` 清单、采集器写法、索引工具 | [`references/工具与脚本.md`](references/工具与脚本.md) |
| 项目怎么放、怎么命名、要不要外发、怎么退役（**建议**） | [`references/项目管理.md`](references/项目管理.md) |
| 外部评审怎么看这套制度、哪些已改 | [`references/提炼速览.md`](references/提炼速览.md) |

## 9. Boundaries

- 不替工作区判断**内容对不对**：体检只能查结构（断链、索引一致、体量、敏感串、协议形式）；
  事实对不对要靠实测与交流测试交叉验证。
- 不碰真实数据：采集器**只读**。
- 不强制统一文件名：**存量文件保留原名**，规则只管新写入。
- 不替你做**判断**：建不建项目、要不要外发、算不算退役，只给建议（`references/项目管理.md`）；
  体检只核对形式，`cards` 项也一样。
- 不绑定实现：脚本是示范，规则才是本体。
