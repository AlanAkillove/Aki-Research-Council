# AGENTS.md — 编码 Agent 约束

在改代码或加功能前先读：

1. [`docs/product/01-prd-summary.md`](docs/product/01-prd-summary.md)
2. [`docs/product/02-architecture.md`](docs/product/02-architecture.md)
3. [`docs/product/03-tech-spec.md`](docs/product/03-tech-spec.md)
4. [`docs/product/04-acceptance-criteria.md`](docs/product/04-acceptance-criteria.md)
5. 涉及 HTML/站点时：[`docs/product/05-ui-design.md`](docs/product/05-ui-design.md)

**字段、限额、状态机以 Tech Spec 为准。** 意图冲突回指 PRD / Architecture。

## 硬禁止

- 提交密钥、`.env` 真值、私有全文到公开产物
- 改写历史报告；反馈与事件只追加 JSONL
- 绕过验收门禁宣称 P1–P4「完成」
- 擅自开启 P4 自动执行 / 训练 / 投稿
- 把 `inference` / `hypothesis` 写成 `fact`
- 使用「首创 / 全新」等绝对新颖性措辞

## 代码与状态位置

- 代码：`src/arc/`
- 配置：`config/`
- 运行状态：`research_state/`（仅 Chair 路径可写正式决策）
- Prompt：`prompts/`（改内容必须升 `prompt_version`）
- 报告：`reports/`（由管线生成）

## 变更纪律

- Schema / 限额变更 → 同步改 Tech Spec 与验收清单相关项
- 重大技术取舍 → 新增 `docs/collab/adr/`
- 用户可见行为 → 更新 `CHANGELOG.md`
- 当前工作 → 更新 `TODO.md` 勾选状态

## 完成一项任务前

对照 [`docs/collab/dod.md`](docs/collab/dod.md)。
