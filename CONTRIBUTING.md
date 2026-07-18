# 贡献指南

## 分支

- `main`：可用文档与稳定基线
- `feat/<topic>` / `fix/<topic>`：短生命周期分支

## 开发前

1. 读 [`AGENTS.md`](./AGENTS.md)
2. 读 [`docs/product/`](./docs/product/) 中与任务相关的文档
3. 在 [`TODO.md`](./TODO.md) 认领或新增条目

## PR 清单

对照 [`docs/collab/dod.md`](./docs/collab/dod.md)。至少说明：

- 动机与用户可见影响
- 是否改动 schema / Prompt / 验收项
- 如何验证（命令或手工步骤）

## 文档真相源

| 问题 | 文档 |
|------|------|
| 产品意图 | `docs/product/01`–`02` |
| 字段与限额 | `docs/product/03` |
| 是否完工 | `docs/product/04` |
| Agent 纪律 | `AGENTS.md` |
| 技术取舍 | `docs/collab/adr/` |

不要复制粘贴两份评分公式；改一处并链接。
