# Prompts

本目录存放各角色 / 任务的 Prompt 模板。

## 版本约定

1. 每个模板文件头或同名 meta 中声明 `prompt_version`（如 `v1`、`v1.1`）。
2. **任何改字都必须升版本号**；run 日志记录所用版本。
3. 旧版本可留在 `prompts/archive/`，便于复现历史报告。

## 建议结构

```text
prompts/
├── README.md          # 本文件
├── ai_paper/
├── math_paper/
├── ai_for_math/
├── skeptic/
├── ideator/
├── chair/
└── archive/
```

## 变更检查

- 输出仍满足 Tech Spec 中对应 Pydantic schema
- 未引入绝对「首创」措辞
- 必要时追加评测分数卡一行（`docs/collab/eval/`）
