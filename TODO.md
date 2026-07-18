# TODO — 任务板

> 阶段是否完工看 [`docs/product/04-acceptance-criteria.md`](docs/product/04-acceptance-criteria.md)。  
> 本文件只跟踪**当前冲刺**；完成后勾选并必要时开下一张卡。

## Now（进行中）

- [x] P1 骨架：`pyproject.toml` + `src/arc` 包结构 + CLI 入口占位
- [x] P1 配置：`config/sources.yaml` / `models.yaml` / `ranking.yaml`
- [x] P1 `research_state` 示例：profile + 项目 + 开放问题
- [x] arXiv 增量抓取客户端 + SQLite PaperStore 持久化
- [x] `arc ingest arxiv` / `arc ingest status` CLI 命令
- [x] 归一化与去重管线（指纹 dedup、状态转换）
- [x] 两阶段筛选（硬过滤 + LLM 多维评分 + composite_score 排名）
- [x] 日报真实数据接入（build_daily_context + run_daily_full）
- [x] feedback.jsonl 写入路径
- [x] 全链路 smoke（arc smoke 覆盖 7 个步骤）

## Next（P1）

_所有 P1 任务已完成，可进入 P2 阶段验收。_

## Later

- [ ] P2 Evidence Pack + Claim Ledger
- [ ] P2 Historian / Skeptic / Liaison
- [ ] P3 Idea 生命周期 + 周会 PPT
- [ ] P4 最小验证（默认关闭）

## Blocked

_无_
