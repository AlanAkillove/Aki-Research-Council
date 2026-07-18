# ADR 0002 — 技术栈修订（去 Quarto/FAISS/LiteLLM 硬依赖）

## 状态

Accepted（部分取代 ADR-0001 第 4、5 条及「向量用本地索引」的默认实现）

## 日期

2026-07-18

## 背景

ADR-0001 锁定了方向正确的原则（SQLite 中心、状态机、Chair 单写），但默认实现选型偏「演示级全家桶」：Quarto + PptxGenJS（Node）+ FAISS + LiteLLM。对本仓库场景（Windows 个人机、Python 单仓、日更批处理、论文量通常 ≪ 10⁵）成本与摩擦过高，且不利 P1 落地。

## 决策对照

| 项 | 原默认 | 现默认 | 理由 |
|----|--------|--------|------|
| 包管理 | 未锁定 | **uv + pyproject.toml** | 锁文件、Windows 友好、快 |
| 语言 | Python 3.11+ | **Python 3.12+**（兼容 3.11 开发） | 类型与标准库更稳；CI 以 3.12 为准 |
| LLM 接入 | LiteLLM 硬依赖 | **`openai` SDK（compatible base_url）+ 自研 `ModelProvider`** | 个人多模型场景用兼容端点即可；LiteLLM 作可选适配器，非必装 |
| 向量检索 | FAISS | **SQLite 存 embedding + NumPy 余弦（MVP）** | 日更千级候选、库内万级足够；免 C++/编译；Windows 零痛苦。规模或延迟不够再评 **sqlite-vec** / **usearch** |
| 全文检索 | FTS5 或 Tantivy | **仅 SQLite FTS5** | 零额外依赖；Tantivy 推迟到语料与排序需求明确后 |
| 日报渲染 | Jinja2 + Quarto | **Jinja2 → Markdown + 自包含 HTML** | 纯 Python；公式用 KaTeX CDN；Quarto 降为可选增强 |
| 周会 PPT | Quarto → PptxGenJS | **python-pptx**（另保留 Markdown 纪要） | 不引入 Node；版式可控；Quarto/PptxGenJS 不再进主路径 |
| 调度 | Actions 或自托管并列 | **本机定时为主，Actions 为辅** | 长 LLM 跑、私有 State、密钥更适合本机；Actions 做轻量 ingest 镜像 / Pages / CI |
| PDF | 未锁定 | **PyMuPDF**；数学优先 arXiv TeX | 抽取质量与依赖平衡优于纯 pypdf；Docling 过重，仅作后备调研 |
| 测试 | 未锁定 | **pytest** | 生态默认 |

**不变**：SQLite + JSONL + Git；显式状态机；Chair 单写；不强绑单一云厂商。

## 替代方案与否决

### 保留 Quarto 作日报主路径

- 利：数学排版、多格式一条龙  
- 弊：外部 CLI、CI/本机环境脆弱、与 Python 发布管线割裂  
- 结论：否决为默认；需要时单篇导出再用

### FAISS / Chroma 作默认向量库

- 利：性能、生态教程多  
- 弊：FAISS 在 Windows 安装摩擦大且过度；Chroma 多一层抽象与依赖  
- 结论：否决为 MVP 默认

### LiteLLM 作必装网关

- 利：统一多厂商  
- 弊：升级碎、调试层多；多数调用已是 OpenAI-compatible  
- 结论：接口层自研；LiteLLM 可选

### 周会用 PptxGenJS

- 利：幻灯片能力强  
- 弊：Python 仓引入 Node 双运行时  
- 结论：否决；用 python-pptx

### 每日全流程默认跑在 GitHub Actions

- 利：免开电脑  
- 弊：cron 延迟、超时、密钥与私有文献风险、长推理贵且不稳  
- 结论：本机为主

### sqlite-vec 作为 MVP 必选

- 利：与 SQLite 一体  
- 弊：仍 pre-v1；Windows 扩展加载/SQLite 版本有坑  
- 结论：列为**升级选项**，不是 Day-1 必装

## 后果

- P1 依赖面显著缩小，更易在 Windows 上复现  
- 向量暴力检索在 1–3 万篇内可接受；需在 Tech Spec 写明升级触发条件（库规模、延迟、过滤复杂度）  
- 站点与 PPT 观感可能暂时朴素，但可行动性与可维护性优先  
- ADR-0001 原则仍有效；本 ADR 修订其实现默认值
