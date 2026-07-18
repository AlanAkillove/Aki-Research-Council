# TODO — 任务板

> 阶段是否完工看 [`docs/product/04-acceptance-criteria.md`](docs/product/04-acceptance-criteria.md)。  
> 本文件只跟踪**当前冲刺**；完成后勾选并必要时开下一张卡。

## Now（进行中）

- [x] P1 骨架：`pyproject.toml` + `src/arc` 包结构 + CLI 入口占位
- [x] P1 配置：`config/sources.yaml` / `models.yaml` / `ranking.yaml`
- [x] P1 `research_state` 示例：profile + 项目 + 开放问题

## Next（P1）

- [ ] arXiv 增量抓取 + SQLite 落库
- [ ] 归一化与去重（DOI / arXiv / 标题指纹）
- [ ] 两阶段筛选（硬过滤 → 多维 JSON 精排）
- [ ] 每日 Markdown + HTML 渲染（模板已有，接真实数据）
- [ ] `feedback.jsonl` 写入路径
- [ ] smoke：ingest → screen → report

## Later

- [ ] P2 Evidence Pack + Claim Ledger
- [ ] P2 Historian / Skeptic / Liaison
- [ ] P3 Idea 生命周期 + 周会 PPT
- [ ] P4 最小验证（默认关闭）

## Blocked

_无_
