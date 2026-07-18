# Definition of Done（定义完成）

关闭 Issue / 合并 PR 前自检：

## 通用

- [ ] 行为符合 [`../product/01-prd-summary.md`](../product/01-prd-summary.md) 原则
- [ ] 若改字段/限额/状态机 → 已更新 Tech Spec
- [ ] 若影响阶段完成定义 → 已更新验收清单勾选说明
- [ ] 无密钥、无未授权全文进入提交
- [ ] 相关测试或 smoke 通过（有则必须）
- [ ] `TODO.md` / Issue 状态已更新
- [ ] 用户可见变化已记入 `CHANGELOG.md`

## 涉及 LLM / Prompt

- [ ] `prompt_version` 已递增
- [ ] 输出仍通过 Pydantic schema
- [ ] 未引入绝对「首创」措辞

## 涉及 Research State

- [ ] 正式状态变更经 Chair 路径
- [ ] JSONL 只追加
- [ ] 历史报告未被改写

## 宣称阶段完成时

- [ ] [`../product/04-acceptance-criteria.md`](../product/04-acceptance-criteria.md) 对应阶段 P*.2 已全部勾选
