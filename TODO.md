# TODO — 任务板

> 阶段是否完工看 [`docs/product/04-acceptance-criteria.md`](docs/product/04-acceptance-criteria.md)。  
> 本文件只跟踪**当前冲刺**；完成后勾选并必要时开下一张卡。

## Now（进行中）

- [x] P1 骨架：`pyproject.toml` + `src/arc` 包结构 + CLI 入口占位
- [x] P1 配置：`config/sources.yaml` / `models.yaml` / `ranking.yaml`
- [x] P1 `research_state` 示例：profile + 项目 + 开放问题
- [x] arXiv 增量抓取客户端 + SQLite PaperStore 持久化
- [x] `arc ingest arxiv` / `arc ingest status` CLI 命令

## Next（P1）

- [ ] 归一化与去重管线（整合 PaperStore + 指纹）
- [ ] 两阶段筛选（硬过滤 → 多维 JSON 精排）
- [ ] 每日 Markdown + HTML 渲染（接入真实论文数据）
- [ ] `feedback.jsonl` 写入路径
- [ ] smoke：ingest → screen → report 全链路

## Later

- [ ] P2 Evidence Pack + Claim Ledger
- [ ] P2 Historian / Skeptic / Liaison
- [ ] P3 Idea 生命周期 + 周会 PPT
- [ ] P4 最小验证（默认关闭）

## Blocked

_无_
