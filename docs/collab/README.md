# 协作文档索引

人与 Agent 共同维护的规范、进度与决策痕迹。产品真相在 [`../product/`](../product/)。

| 文档 | 作用 |
|------|------|
| [runbook.md](./runbook.md) | 故障排查与重跑 |
| [data-model.md](./data-model.md) | 数据模型速查（短版） |
| [dod.md](./dod.md) | 定义完成（Issue / PR 关闭前） |
| [ci.md](./ci.md) | CI 检查说明 |
| [adr/](./adr/) | 架构决策记录（含 [0002 技术栈修订](./adr/0002-stack-revision.md)） |
| [eval/](./eval/) | 评测口径与分数卡 |
| [postmortems/](./postmortems/) | 误判 / 事故复盘 |
| [sessions/](./sessions/) | Agent 会话结论摘要（可选） |

## 仓库根协作入口

| 路径 | 作用 |
|------|------|
| [`../../AGENTS.md`](../../AGENTS.md) | 编码 Agent 硬约束 |
| [`../../.cursor/rules/arc.mdc`](../../.cursor/rules/arc.mdc) | Cursor 规则 |
| [`../../TODO.md`](../../TODO.md) | 当前任务板 |
| [`../../CHANGELOG.md`](../../CHANGELOG.md) | 用户可见变更 |
| [`../../CONTRIBUTING.md`](../../CONTRIBUTING.md) | 贡献与 PR 流程 |
| [`../../SECURITY.md`](../../SECURITY.md) | 安全策略 |
| [`../../CODEOWNERS`](../../CODEOWNERS) | 评审责任（可选） |
| [`../../.env.example`](../../.env.example) | 环境变量名 |
| [`../../prompts/README.md`](../../prompts/README.md) | Prompt 版本约定 |

## 进度三层

1. 阶段门禁 → [`../product/04-acceptance-criteria.md`](../product/04-acceptance-criteria.md)  
2. 当前冲刺 → [`../../TODO.md`](../../TODO.md)  
3. 决策痕迹 → `adr/` + `CHANGELOG` + `research_state/decisions.jsonl`
