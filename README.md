# agent-memory-kit —— 工作区记忆制度（技能 + 工具包）

> 英文版 / English: [README.en.md](README.en.md)

给"长期和 AI 一起干活的目录"用的一套制度：**冷热记忆分离、六区落盘、易变数字交脚本、
定型内容进手册、多智能体测试走协议**。既是 DSH 技能（`SKILL.md`），也是一套可直接执行的脚本。

## 为什么做这个

聊天记录不是记忆：会话一压缩、一换窗口，上下文就断了。这套东西把"该长期记住的"拆成三层落盘，
让任何一次新会话只要读 `AGENTS.md` 的导航表，就能重建全部上下文；也让两个智能体协作时
**谁写了什么**是可查的，而不是靠互相信任。

## 目录

```
agent-memory-kit/
├── SKILL.md                 # 技能入口：规则摘要 + 导航 + 工作流（< 150 行）
├── references/              # 细则：记忆制度 / 交流协议 / 隐私与密钥 / 工具与脚本 / 提炼速览（外部评审·去代码版）
├── scripts/
│   ├── _common.py           # 根定位、配置读取、报告器（被下面几个脚本共用）
│   ├── memory_doctor.py     # 体检：断链/索引/体量/结论前置/敏感串/协议/命名
│   ├── state_snapshot.py    # 生成 STATE.md（易变数字的唯一出处）
│   ├── new_exchange.sh      # 建受控交流测试目录
│   ├── bootstrap.sh         # 在新工作区铺开制度
│   └── collectors/          # 可选的示例采集器（按你的项目自行增删，如某行情库 / 某服务的路由）
├── templates/               # 六区 README、AGENTS.md、settings.md、exchange 模板、薄壳
└── VERSION
```

## 安装 / 启用（取决于你的 harness）

本技能本身是 **harness 无关的**——纯 Markdown + 脚本，最初随一个本地 harness（DSH）开发，
但同样可以放进任何会读 `SKILL.md` 的智能体环境。以 DSH 为例：把技能本体放一处，再软链到它的技能目录即可；
具体路径按你的环境调整，下文命令里的 `~/.dsh/skills/agent-memory-kit/` 换成你实际的技能目录就行。
启用方式也看运行时（如 DSH 下在会话技能里勾选对应 slug）。

## 用法

在任何工作区：

```bash
python3 ~/.dsh/skills/agent-memory-kit/scripts/memory_doctor.py --root .
python3 ~/.dsh/skills/agent-memory-kit/scripts/state_snapshot.py --root .
```

新工作区开局：

```bash
bash ~/.dsh/skills/agent-memory-kit/scripts/bootstrap.sh --root /path/to/new-ws --preset <你的项目> --name 我的工作区
```

装完之后工作区里会有 `scratch/memory-tooling/{memory_doctor.py,state_snapshot.py,new_exchange.sh}` ——
它们是**薄壳**，转发到本技能里的实现，所以逻辑只有一份（别在薄壳里改逻辑）。

## 设计取舍

- **技能不知道具体项目**：项目差异全在 `<工作区>/.memory-kit.toml`（阈值、敏感串豁免、STATE 采集器）。
- **默认严格**：敏感串默认一律 ❌，豁免要在配置里显式写。
- **只读**：采集器不改被采集的东西；有副作用的探测先挡住。
- **薄壳而非副本**：工作区保留命令入口，实现只有一份；技能本体同样只有一份（储存库），改完即生效。
- **体检查得到形式，查不到事实**：事实要靠实测与 `exchange/` 交叉验证 —— 这一点写在技能边界里。

## 隐私

本目录**不含任何凭据**：模板里全部是占位符。自检：

```bash
python3 scripts/memory_doctor.py --root . --only secrets
```
