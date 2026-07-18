# Runbook — 运维与排障

> 实现落地后按实际命令更新本节。当前为约定草案。

## 日常

| 场景 | 动作 |
|------|------|
| 跑每日流水线 | （待定）`arc daily` 或 Actions `daily_council.yml` |
| 只重跑报告 | 使用已有 `data/normalized/`，跳过 ingest |
| 只重抓数据 | 跑 `daily_ingest.yml`；失败保留上次 raw |

## 降级策略

1. 采集失败 → 保留上次 raw，报告标 `partial`
2. 精排失败 → 仅输出硬筛选 TopN + 警告
3. 全文失败 → 回退摘要级分析，标注缺失证据
4. Chair 失败 → 不写正式 State，仅输出草稿报告

## 常见问题

### 日报为空或过少

- 检查 `config/sources.yaml` 类别与日期游标
- 检查 API 限流 / 密钥
- 查看 run 日志 `failures`

### 重复推荐同一论文

- 查归一化主键：DOI > arXiv > OpenReview > S2 > 标题指纹
- 查是否未识别 version update

### 判断无来源 / 幻觉措辞

- 核对 Claim Ledger 类型
- 回放对应 `prompt_version` 与 Evidence Pack
- 记入 `docs/collab/postmortems/`

### 成本暴涨

- 核对 `fulltext_analyzed` / `llm_screened` 限额
- 查是否误走 Daily Deep

## 日志位置（规划）

```text
data/raw/
data/normalized/
reports/daily/
research_state/ 下 JSONL
runs/ 或 SQLite run 表
```
