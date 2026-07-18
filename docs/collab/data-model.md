# 数据模型速查

完整字段见 [`../product/03-tech-spec.md`](../product/03-tech-spec.md)。本文仅给 Agent 快速对齐。

## 核心对象

| 对象 | 主键示例 | 要点 |
|------|----------|------|
| Paper | `canonical_id` | 版本合并；更新 ≠ 新论文 |
| Evidence | `EV-...` | 须有 location + source_tier A–D |
| Claim | `CLM-...` | 类型：fact / author_claim / external_claim / inference / hypothesis / recommendation |
| Idea | `IDEA-...` | signal→…→active_project；rejected 不可删 |
| Decision | `object_id` + verdict | READ/TRY/WATCH/ARCHIVE/NO-GO/UPDATE |
| Question | `Q-...` | 挂 project；含正反证据 |
| Project | `project_id` | 约束、死亡条件、已知失败 |
| Run | `run_id` | git、模型、token、成本、partial/failed |

## Claim 写入规则

- 无 `EV-...` 不得标 `fact`
- 写入正式 Research State 须 `approved_by: chair`

## Idea 阶段

```text
signal → hypothesis → candidate → validated_candidate → active_project
任意 → rejected（保留理由与复活条件）
```

## 日报限额

```text
candidates≤200 · llm_screened≤30 · fulltext≤5
featured≤3 · new_ideas≤1 · actions≤3
```

## 论文主键优先级

```text
DOI > arXiv ID > OpenReview forum ID > Semantic Scholar ID > 标题指纹
```
