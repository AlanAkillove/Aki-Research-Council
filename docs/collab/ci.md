# CI 说明

> Workflows 落地后更新本页命令与必绿检查列表。

## 规划中的检查

| 检查 | 目的 |
|------|------|
| lint / format | 代码风格 |
| typecheck | 类型 |
| unit tests | schema、去重、评分纯函数 |
| schema smoke | Pydantic 样例合法 |
| ingest dry-run | 不调付费 API 或使用 mock |
| docs link check（可选） | 文档相对链接 |

## 规划 Workflows

见 Tech Spec：

```text
daily_ingest.yml
daily_council.yml
weekly_meeting.yml
monthly_retro.yml
manual_topic_review.yml
rebuild_site.yml
evaluation.yml
```

PR 合并建议至少：lint + unit + schema smoke。

## 本地等价命令（待填）

```bash
# 示例占位
# uv run ruff check .
# uv run pytest
# uv run arc smoke
```
