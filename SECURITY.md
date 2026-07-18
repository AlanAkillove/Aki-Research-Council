# Security Policy

## 报告

若发现密钥泄漏、私有文献被公开、或依赖严重漏洞，请勿在公开 Issue 贴敏感内容；改用私有渠道联系维护者。

## 承诺做法

- 密钥仅存环境变量或 CI secrets；仓库只保留 [`.env.example`](./.env.example)
- 不绕过付费墙；不在 GitHub Pages 再分发无授权全文
- `research_state/` 含私有笔记时，默认不发布到公开站点（或先脱敏）
- 依赖告警（Dependabot 等）启用后优先处理高危项

## 禁止

- 将 `.env`、API Key、Cookie、付费 PDF 原文提交进 Git
- 在公开报告中粘贴未授权全文段落超出合理引用范围
