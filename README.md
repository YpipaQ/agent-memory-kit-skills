# agent-memory-kit-skills

**给"长期和 AI 一起干活的目录"用的一套记忆制度。** 规则写短、事实只写一遍、易变数字交给脚本 ——
任何一次新会话，读一张导航表就能把上下文接回来。

[English](README.en.md) ｜ [Issues](https://github.com/YpipaQ/agent-memory-kit-skills/issues) ｜ 版本 2.0.0 ｜ MIT

---

## 这是什么

聊天记录不是记忆。会话一压缩、一换窗口、或把活交给另一个智能体，此前定下的东西就得从头再问一遍。

这套制度把"该长期记住的"**分层放到磁盘上**，于是：

- 新会话读 `AGENTS.md` 里的一张导航表就能重建上下文；
- 一个事实只存在一个文件里，别处用链接指过去；
- 经常变的数字由脚本生成，不手写；
- 两个人（或两个智能体）协作时，"谁写了什么、验到哪一层"是可查的，而不是靠互相信任。

它是纯 Markdown ＋ 脚本：没有框架、没有服务、没有需要一直开着的运行时。

## 它对付的六种坏法

| 常见的坏法 | 这里的药 |
| --- | --- |
| 同一件事写在好几处，改一处忘一处 | 事实只写一次，别处只放链接 |
| 热记忆越写越长（它每一步都要被注入） | 热记忆只留规则与导航，事实挪出去 |
| 笔记只进不出，最后想"记住一切" | 台账与散文分开，按范围取用 |
| 索引写在给人读的文档里，早晚撞死行数上限 | 台账进 JSON，README 只留规则与"活窗口" |
| 复核没有分工，结论是谁写的说不清 | 出题/作答走 `exchange/` 协议 |
| 同一份东西存多处（真身/镜像/备份），各自演化 | 一处真身 ＋ 登记卡，"为了同步而同步"的机制退役 |

## 30 秒上手

```bash
git clone https://github.com/YpipaQ/agent-memory-kit-skills.git
KIT="$PWD/agent-memory-kit-skills"

# 给一个新工作区铺开制度（默认六区；需要时加挂 projects/、data/）
bash "$KIT/scripts/bootstrap.sh" --root /path/to/new-ws --name 我的工作区

# 体检：跑到 ❌ 清零
python3 "$KIT/scripts/memory_doctor.py" --root /path/to/new-ws
```

铺开时还会往 `scratch/memory-tooling/` 放四个**薄壳** —— `memory_doctor.py`、`state_snapshot.py`、
`memory_query.py`、`new_exchange.sh`。它们转发到技能里的实现，所以逻辑只有一份：
**别在薄壳里改逻辑。**

## 装好之后你得到什么

**六个区**（默认；`projects`、`data` 是常见的加挂区）：

| 区 | 放什么 |
| --- | --- |
| `memory/` | 在办的事、试出的结论、失败的尝试、待办 —— 你要**读**的叙述 |
| `handbook/` | 已定型、实测通过、可照做的流程与参数 —— 你要**照做**的速查 |
| `exchange/` | 出题/作答的受控交流（多智能体测试）—— 你要**传**的话 |
| `scratch/` | 可复跑的脚本、基准、产物 —— 你要**跑**（也可能整区弃掉）的 |
| `archive/` | 会被滚动窗口挤掉、不可再生的数据快照 —— 你要**留**的数据 |
| `trash/` | 用过不再读的产物；`mv` 不 `rm` —— 你要**扔**的 |

**三层内容分离** —— 这是防漂移的关键：

| 层 | 文件 | 里面写什么 | 怎么更新 |
| --- | --- | --- | --- |
| 热 | `AGENTS.md` | 提示词、规则、长期习惯、导航表 | 手改，越短越好 |
| 半稳定 | `memory/settings.md` | 端点、凭据位置、路径、模型名、口径坑 | 手改 |
| 易变 | `STATE.md` | 体积、行数、缓存、归档、磁盘、设备 | **脚本生成，别手改** |

**索引是数据，README 是规则。** 一行一条的台账写进给人读的 README，就会随条目数无限膨胀，
早晚撞死行数上限。所以台账进 `memory/index/YYYY-MM.json`（机器读，涨到几千条也只是几百 KB），
README 只留规则和一张由脚本生成、大小恒定的"活窗口"。正文永远保留 ——
结构化索引是为了**默认只取需要的**，不是为了删东西。

**项目：一处真身 ＋ 登记卡**（加挂 `projects/` 区时的推荐形态，由 `.memory-kit.toml` 的 `[projects]` 决定）：

- **真身只有一处** —— 代码、测试、产物都在那（`embedded` 就在 `projects/<名>/`；
  `card` 则在工作区外 `truth_root/<名>/`），**改动只在那里**；
- 工作区里只放一张 **≤40 行的登记卡**（真身路径／类别／可见性／状态／git／指针，不放代码、不复制说明）；
- **判断类的事（建不建、要不要外发、算不算退役）不写进脚本** —— 见
  [`references/项目管理.md`](references/项目管理.md)（自然语言的建议）。体检的 `cards` 项
  **只核对形式**：卡在不在、真身路径指不指得到、真身根下有没有漏登记的。

## 常用命令

下文 `<工作区>` 换成你的工作区路径；脚本路径按你实际放技能的位置替换。

| 目的 | 命令 |
| --- | --- |
| 体检一个工作区 | `python3 scripts/memory_doctor.py --root <工作区>` |
| 只查敏感串 | `python3 scripts/memory_doctor.py --root <工作区> --only secrets` |
| 只核对登记卡 ↔ 真身 | `python3 scripts/memory_doctor.py --root <工作区> --only cards` |
| 生成易变数字快照 | `python3 scripts/state_snapshot.py --root <工作区>` |
| 索引：重建 / 校验 / 活窗口 / 体量 | `python3 scripts/memory_query.py --root <工作区> [--rebuild\|--check\|--refresh\|--stats]` |
| 按范围检索 / 结账 | `python3 scripts/memory_query.py --root <工作区> [--since D --grep 词 \| --stale 30 \| --delete --path P \| --prune --before D --apply]` |
| 建交流测试目录 | `bash scripts/new_exchange.sh --root <工作区> "YYYY-MM-DD-主题" "说明"` |
| 铺开各区 | `bash scripts/bootstrap.sh --root <新目录> [--areas memory,...,projects,data] [--collector <采集器.py>] [--name 名字]` |
| 真身放工作区外 | `bash scripts/bootstrap.sh --root <新目录> --areas memory,...,projects --projects-mode card --truth-root /真身根路径` |

退出码：体检 `0` 无阻断 / `1` 有 ❌；`--check` 一致 `0` / 不一致 `1`；
`new_exchange.sh` `2` 已存在 / `3` 模板缺失 / `4` 目录名不合规。

## 装到你的环境里

本技能**与 harness 无关**：纯 Markdown ＋ 脚本，只要那个环境会读 `SKILL.md` 就能生效。三种接法任选：

1. **直接放置** —— 把整个 `agent-memory-kit-skills/` 目录放进你的技能目录
   （例如 Claude Code 的 `~/.claude/skills/agent-memory-kit-skills/`、DSH 的 `~/.dsh/skills/`），
   重启会话即生效，**不需要包管理器**。
2. **npm** ——

   ```bash
   npm install agent-memory-kit-skills
   ```

   再把 `node_modules/agent-memory-kit-skills` 链接或复制到技能目录。
3. **软链** —— 技能本体只放一处，链到技能目录。薄壳不写死路径，
   重跑一次 `bootstrap.sh` 就会按当前环境填上正确路径。

## 设计取舍

- **技能不知道你的项目**：项目差异全在 `<工作区>/.memory-kit.toml`（区清单、阈值、敏感串豁免、STATE 采集器）。
- **默认严格**：敏感串默认一律 ❌，豁免要显式写进配置 —— 豁免是需要人确认的决定，不是脚本的默认宽容。
- **采集器只读**：不改被采集的东西；有副作用的探测先挡住。
- **薄壳而非副本**：工作区保留命令入口，实现只有一份。
- **零第三方依赖**：Python 3 标准库（≥ 3.8；有 `tomllib` 就用，没有就走内置的极简 TOML 子集）
  ＋ 一个 POSIX shell。默认配置 `[state] tools = []`，**不调任何外部程序**；
  平台数字探不到就如实写一句，绝不填"看着正常"的假数字。
- **体检查得到形式，查不到事实**：事实要靠实测，以及 `exchange/` 里的交叉验证。
- **脚本是参考实现**：规则才是本体 —— 你完全可以用自己环境的原生工具重写它们。

## 边界（它不做什么）

- 不替你判断**内容对不对**：体检只查结构（断链、索引一致、体量、敏感串、协议形式）。
- 不碰真实数据：采集器**只读**。
- 不强制统一文件名：**存量文件保留原名**，规则只管新写入。
- 不替你做判断：建不建项目、要不要外发、算不算退役，只给建议，不强制执行。

## 隐私

本仓库**不含任何凭据**：模板里全是占位符。自检：

```bash
python3 scripts/memory_doctor.py --root . --only secrets
```

细节见 [`references/隐私与密钥.md`](references/隐私与密钥.md)。

## 目录结构

```
agent-memory-kit-skills/
├── SKILL.md                 # 技能入口：规则摘要 + 导航 + 工作流
├── README.md / README.en.md # 中文 / 英文说明
├── references/              # 细则：记忆制度 / 项目管理 / 交流协议 / 隐私与密钥 / 工具与脚本 / 提炼速览
├── scripts/
│   ├── _common.py           # 公共件：定位工作区、读配置、输出报告
│   ├── memory_doctor.py     # 体检：断链 / 索引一致 / 体量 / 结论前置 / 敏感串 / 协议 / 命名
│   ├── memory_query.py      # 索引台账：重建 / 校验 / 刷新活窗口 / 按范围检索
│   ├── state_snapshot.py    # 生成 STATE.md（易变数字的唯一出处）
│   ├── new_exchange.sh      # 建一个受控交流（出题）目录
│   ├── bootstrap.sh         # 在新工作区铺开整套制度
│   └── collectors/example.py# 示例采集器：只读
├── templates/               # AGENTS.md、settings、各区 README、exchange、薄壳、项目登记卡
├── VERSION
└── package.json
```

## 许可

MIT —— 见 [`LICENSE`](LICENSE)。

---

> **说明**：本项目由智能体在日常使用中逐步积累而成 —— 规则、脚本与判据都来自实际跑过的任务，
> 而非先写文档再实现。
