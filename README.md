# ARC — Aki Research Council

持续型个人研究委员会：用 Research State 跟踪项目与约束，将新证据转化为研究决策与最小验证任务。

## 快速开始

```bash
# 需要 Python 3.12+ 与 uv
cd D:\DesktopDocs\projects\aki-research-council
uv sync --extra dev
copy .env.example .env   # 填入密钥（勿提交）

uv run arc doctor
uv run arc smoke
uv run arc daily --skeleton
```

生成的骨架日报在 `reports/daily/`。

## 文档

| 你想… | 去哪 |
|------|------|
| 了解产品 | [`docs/product/01-prd-summary.md`](docs/product/01-prd-summary.md) |
| 看架构 | [`docs/product/02-architecture.md`](docs/product/02-architecture.md) |
| 查字段/限额 | [`docs/product/03-tech-spec.md`](docs/product/03-tech-spec.md) |
| 看是否做完 | [`docs/product/04-acceptance-criteria.md`](docs/product/04-acceptance-criteria.md) |
| UI 视觉 | [`docs/product/05-ui-design.md`](docs/product/05-ui-design.md) |
| 协作规范 / 排障 | [`docs/collab/README.md`](docs/collab/README.md) |
| 当前任务 | [`TODO.md`](TODO.md) |
| 给 Agent 的纪律 | [`AGENTS.md`](AGENTS.md) |

```text
docs/
├── product/   # PRD · Architecture · Tech Spec · Acceptance · UI
└── collab/    # ADR · Runbook · DoD · Eval · Postmortems …
```

## 仓库布局（实现）

```text
src/arc/           # 包代码
config/            # sources / models / ranking / …
research_state/    # 项目与开放问题（示例已入库）
templates/         # Jinja2 + CSS tokens
reports/           # 生成物
tests/
```

## 状态

- 骨架已就位：`uv run arc smoke` 应通过
- 实时 arXiv ingest / 两阶段筛选尚未实现（见 `TODO.md` Next）
- 选型见 [ADR-0002](docs/collab/adr/0002-stack-revision.md)
- 远程：<https://github.com/AlanAkillove/Aki-Research-Council>

## 开发

见 [`CONTRIBUTING.md`](CONTRIBUTING.md)。实现冲突时：意图看 product 01/02，字段看 03，完工看 04，视觉看 05。
