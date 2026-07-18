# 评测（Eval）

## 口径

指标定义以 [`../../product/03-tech-spec.md`](../../product/03-tech-spec.md) 第 13 节为准。阶段门槛见 [`../../product/04-acceptance-criteria.md`](../../product/04-acceptance-criteria.md)。

## 离线集

| 项 | 约定 |
|----|------|
| 规模目标 | ≥100 篇（可累积） |
| 标签 | 强相关 / 弱相关 / 无关 / 已知重复 / 值得精读 / 方法可迁移 |
| 存放 | （待定）`data/eval/` — 不含付费全文 |

## 分数卡

| 日期 | Precision@5 | Duplicate Rate | Unsupported Claim Rate | 备注 |
|------|-------------|----------------|--------------------------|------|
| — | — | — | — | 尚未跑评测 |

## 变更规则

改排序特征或 Prompt 后，应重跑相关指标并追加一行分数卡，勿覆盖历史行。
