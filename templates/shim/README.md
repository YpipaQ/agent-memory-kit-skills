# 记忆维护工具（{{工作区}}）

这里是**命令入口**：这几个薄壳脚本都只是转发到技能 `agent-memory-kit` 里的实现。
**逻辑只有一份**，改逻辑去技能目录改，不要在这里改 —— 否则两边会漂移。

```bash
python3 scratch/memory-tooling/memory_doctor.py      # 记忆体检（断链/索引一致/体量/结论前置/敏感串/协议/命名）
python3 scratch/memory-tooling/memory_query.py --rebuild --refresh   # 写/删笔记后：重建台账 + 刷新 README 活窗口
python3 scratch/memory-tooling/memory_query.py --since 2026-09-01 --grep 关键词  # 按范围取，别全量读
python3 scratch/memory-tooling/memory_query.py --stats               # 阅读面体量（超预算该结账）
python3 scratch/memory-tooling/memory_query.py --prune --before 2026-08-01     # 干跑；--apply 才 mv 到 trash/
python3 scratch/memory-tooling/state_snapshot.py     # 生成根目录 STATE.md（易变数字的唯一出处）
bash    scratch/memory-tooling/new_exchange.sh "YYYY-MM-DD-主题" "说明"   # 建交流测试目录
```

**索引与散文分离**：全量台账在 `memory/index/YYYY-MM.json` 与其他区的 `index.json`（**数据**，不参与 md 行数规则）；
各区 README 只放**规则 + 活窗口**（近 N 天 + 未结项，`--refresh` 生成，有界）。
所以**写笔记不用再手动改 README**，跑 `--rebuild --refresh` 即可。

薄壳怎么找技能：环境变量 `MEM_KIT_HOME` → 本文件里的 `{{KIT}}` 占位符（铺开制度时被替换成**本机实际路径**）。
技能**只放一份**，所以**改完即生效、没有同步步骤**；想让某个工作区临时跑另一份，设 `MEM_KIT_HOME=<技能目录>`。
（薄壳里不写死任何系统路径 —— 换机器、换 harness 只要重跑一次 `bootstrap.sh`。）

## 本工作区的项目差异

差异**不写在脚本里**，都写在根目录 `.memory-kit.toml`（阈值、敏感串豁免、STATE 采集器、工具版本）。

## 采集器（collectors/）

STATE.md 的项目专属段落由采集器产生：每个 `.py` 暴露 `collect(root, cfg) -> list[str]`，返回 markdown 行。
技能只自带一个**通用示例** `collectors/example.py`（默认不登记）；**项目专用的采集器一律由工作区自备**
（`bootstrap.sh --collector <文件>` 会把它拷进来并登记）：

```toml
[state]
collectors = ["scratch/memory-tooling/collectors/你的.py"]
```

采集器崩了只会在 STATE.md 里显示一行错误，不会让生成失败；
**只采集、不改动被采集的东西**，需要外部命令时先判断"在不在"，不在就如实写一句。

## 惯例

- 改完 `AGENTS.md` / 冷记忆 / 各区 README 后跑一次体检（❌ 必须清零，⚠️ 看情况）。
- 库/盘/配置变动后跑一次 `state_snapshot.py`（或 `--check`）。
- 体检全绿 ≠ 内容正确：链接和格式能自动查，**事实要靠交流测试（`exchange/`）交叉验证**。
