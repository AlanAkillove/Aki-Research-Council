# ARC — Aki Research Council

持续型个人研究委员会：用 Research State 跟踪项目与约束，将新证据转化为研究决策与最小验证任务。

## 快速入口

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

## 文档结构

```text
docs/
├── product/   # PRD · Architecture · Tech Spec · Acceptance · UI
└── collab/    # ADR · Runbook · DoD · Eval · Postmortems …
```

## 状态

当前以文档与协作基建为主（产品 v0.3 / 选型见 [ADR-0002](docs/collab/adr/0002-stack-revision.md)）。按验收清单 **P1 → P4** 推进；流水线尚未可运行。

远程仓库：<https://github.com/AlanAkillove/Aki-Research-Council>（SSH 提交）。

配置密钥时复制 [`.env.example`](.env.example) 为 `.env`（勿提交）。

## 开发

见 [`CONTRIBUTING.md`](CONTRIBUTING.md)。实现冲突时：意图看 product 01/02，字段看 03，完工看 04。
