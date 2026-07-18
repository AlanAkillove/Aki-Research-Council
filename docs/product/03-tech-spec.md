# ARC 技术规格（Tech Spec）

> **依据**：[`01-prd-summary.md`](./01-prd-summary.md) · [`02-architecture.md`](./02-architecture.md)  
> **验收**：[`04-acceptance-criteria.md`](./04-acceptance-criteria.md)  
> **版本**：v0.3  
> **性质**：可实现约定（字段、流程、边界）。变更须同步改测试与验收项。  
> **选型依据**：[ADR-0002](../collab/adr/0002-stack-revision.md)

---

## 1. 技术栈（锁定）

### 1.1 默认栈

```yaml
language: Python 3.12+          # 本地可 3.11 开发；CI 以 3.12 为准
package_manager: uv             # pyproject.toml + lockfile
config: YAML
schemas: Pydantic v2
cli: Typer
http: httpx + asyncio
metadata_store: SQLite
event_log: JSONL                # 只追加
fulltext_search: SQLite FTS5
vector_index: sqlite_blobs + numpy_cosine   # MVP；见升级条件
embeddings_api: OpenAI-compatible 或本地小模型
llm_access: openai_sdk_compatible + ModelProvider
pdf: PyMuPDF                    # 数学论文优先 arXiv TeX
daily_render: Jinja2 → Markdown + self-contained HTML  # KaTeX CDN；主题见 05-ui-design
weekly_slides: python-pptx + Markdown minutes
ui_theme: docs/product/05-ui-design.md   # Claude 暖色编辑风 token
scheduler_primary: local cron / Task Scheduler / 手动
scheduler_secondary: GitHub Actions           # CI、Pages、可选轻量 ingest
site: 本地静态 或 GitHub Pages（脱敏后）
test: pytest
```

业务逻辑不得绑死单一厂商 SDK；统一：

```python
class ModelProvider:
    async def generate(self, task: str, schema: type, context: dict) -> object: ...
```

推荐实现：官方 `openai` Python SDK + 可配置 `base_url`（兼容代理 / 第三方 / 本地 vLLM）。**不**将 LiteLLM 列为必装依赖。

### 1.2 明确不作为默认依赖

| 组件 | 为何不默认 | 何时可再引入 |
|------|------------|--------------|
| Quarto | 外部 CLI，割裂 Python 管线 | 需要精美多格式出版时可选 |
| PptxGenJS | 引入 Node 双运行时 | 不用；周会用 python-pptx |
| FAISS | Windows 安装重、MVP 过杀 | 库规模与延迟证明需要时再评 |
| LiteLLM | 额外抽象与升级面 | 多厂商差异大到自研适配器不够时 |
| Tantivy | 额外原生依赖 | FTS5 排序/规模不够时 |
| Docling | 重；非日报主路径 | PDF 版面极复杂且 PyMuPDF 失败时 |
| Postgres / 独立向量 DB | MVP 过重 | 单机 SQLite 成为瓶颈后 |

### 1.3 向量检索升级触发条件

同时满足再开 ADR 评估 sqlite-vec / usearch 等：

- 持久论文向量 ≫ 2×10⁴，或单次检索 P95 延迟不可接受；或
- 需要复杂元数据预过滤 + ANN 的组合查询，NumPy 扫描维护成本过高。

---

## 2. 仓库结构

```text
aki-research-council/
├── docs/
│   ├── product/                  # 产品四件套
│   └── collab/                   # 协作：ADR、Runbook、评测等
├── config/
│   ├── sources.yaml
│   ├── topics.yaml
│   ├── models.yaml
│   ├── ranking.yaml
│   └── report.yaml
├── research_state/               # 运行时中心状态（可部分入 Git）
├── src/arc/
│   ├── ingestion/
│   ├── normalization/
│   ├── retrieval/
│   ├── evidence/
│   ├── council/
│   ├── memory/
│   ├── ranking/
│   ├── reporting/
│   ├── evaluation/
│   └── cli.py
├── prompts/
│   ├── ai_paper/
│   ├── math_paper/
│   ├── ai_for_math/
│   ├── skeptic/
│   ├── ideator/
│   └── chair/
├── schemas/                      # 可选：导出的 JSON Schema；权威模型在 src/arc/schemas/
├── templates/
├── site/
├── reports/
├── data/
│   ├── raw/
│   ├── normalized/
│   ├── evidence/
│   └── indexes/
├── tests/
├── scripts/
└── .github/workflows/
```

包名：`arc`。导入根：`src/arc`。

---

## 3. 流水线状态机

每篇候选论文 / 每次 run 显式状态：

```text
INGESTED
→ NORMALIZED
→ SCREENED
→ EVIDENCE_READY
→ REVIEWED
→ CHAIR_DECIDED
→ PUBLISHED
```

硬性要求：

- 每步结构化 I/O（Pydantic）
- 可单独重试；不覆盖上一步原始产物
- 记录 `model_id`、`prompt_version`、`timestamp`
- 失败允许降级：生成标记为 `partial` 的报告

---

## 4. 数据源与抓取

### 4.1 arXiv 初始类别

```yaml
ai:
  - cs.AI
  - cs.LG
  - cs.CV
  - cs.CL
  - cs.MA
  - cs.LO
mathematics:
  - math.CO
  - math.MG
  - math.OC
  - math.PR
  - math.RA
  - math.LO
```

类别仅召回，不作最终相关性。须缓存重复查询，遵守官方频率建议。

### 4.2 其他一级源

| 源 | 用途 |
|----|------|
| OpenReview API 2（旧会或 API 1） | Notes：稿/评/复/决 |
| Semantic Scholar | 引用、相似、正负种子推荐、SPECTER2 |
| OpenAlex | 主题层级、聚合趋势 |
| Crossref | DOI / 期刊 / 撤稿或更新 |
| Unpaywall | 合法 OA 定位 |

### 4.3 二级源

GitHub（release / issue / discussion）、HF、实验室博客、会议页——写入信号表，默认不可单独支撑 `fact` 型 Claim。

### 4.4 Workflows

```text
daily_ingest.yml
daily_council.yml
weekly_meeting.yml
monthly_retro.yml
manual_topic_review.yml
rebuild_site.yml
evaluation.yml
```

采集失败：保留上次 raw。报告失败：不重抓全源。

---

## 5. 论文实体与版本归一

### 5.1 Paper（逻辑主键优先级）

```text
DOI > arXiv ID > OpenReview forum ID > Semantic Scholar ID > 标题指纹
```

标题指纹：小写、去标点、去停用词 + 作者重叠 + 编辑距离 + 摘要嵌入相似度。

### 5.2 Paper schema（摘要）

```yaml
paper:
  canonical_id: string          # 归一后主键
  doi: string | null
  arxiv_id: string | null
  openreview_id: string | null
  semantic_scholar_id: string | null
  openalex_id: string | null
  title: string
  authors: [string]
  categories: [string]
  abstract: string
  pdf_url: string | null
  source_url: string | null
  code_urls: [string]
  versions: [VersionRef]
  related_projects: [string]
  processing_status: metadata_only | screened | evidence_ready | reviewed
```

### 5.3 版本更新事件

识别为 `paper_version_update`，**不是**新论文。必须生成差异报告字段：

- title_changed / abstract_changed
- theorems_or_experiments_added
- authors_changed
- review_responses_added
- conclusion_strength: strengthened | weakened | unchanged | unknown

---

## 6. Evidence Pack 与 Claim Ledger

### 6.1 Evidence

```yaml
evidence:
  id: EV-...
  paper_id: string
  location: { page?: int, section?: string, table?: string, tex_env?: string }
  content: string
  evidence_type: theorem | experiment | ablation | review | code | other
  source_tier: A | B | C | D
  extraction_method: tex | pdf_text | layout | ocr | api
  confidence: float  # 0-1
```

全文处理优先级：`arXiv TeX > PDF 文本 > 布局解析 > OCR`。仅对进入深度分析的论文取全文。

### 6.2 Claim

```yaml
claim:
  claim_id: CLM-...
  text: string
  type: fact | author_claim | external_claim | inference | hypothesis | recommendation
  confidence: low | medium | high
  evidence_for: [EV-...]
  evidence_against: [EV-...]
  generated_by: scout | historian | skeptic | liaison | ideator | chair | system
  approved_by: chair | null      # 写入正式 State 前必须 chair
  paper_id: string | null
```

规则：后续 Agent 引用论文必须指向 Evidence Pack 中的 `EV-...`；无证据不得写 `fact`。

### 6.3 Evidence Pack

```text
论文主张
→ 支持位置
→ 作者承认限制
→ 外部审稿/复现
→ 相近工作异同
```

---

## 7. 筛选与排序

### 7.1 阶段一：硬筛选（无强推理模型）

- 日期/版本去重与归一
- 已读 / 已拒绝检查
- 类别、关键词、作者白名单；负面关键词
- 与项目 & 开放问题向量相似度
- Semantic Scholar 正负种子推荐
- 引用图邻居召回

### 7.2 阶段二：结构化精排（约 20–40 篇）

模型必须输出多维 JSON（禁止只给总分），例如：

```json
{
  "topic_relevance": 0.0,
  "project_relevance": 0.0,
  "method_transferability": 0.0,
  "novelty_signal": 0.0,
  "feasibility": 0.0,
  "evidence_quality": 0.0,
  "redundancy": 0.0,
  "recommended_action": "ignore"
}
```

综合分（初始先验，可被反馈覆盖）：

\[
S(p)=w_R R + w_L L + w_E E + w_F F + w_N N + w_T T - P
\]

- \(R\) 问题相关性 · \(L\) 杠杆 · \(E\) 证据质量 · \(F\) 可行性  
- \(N\) 潜在新颖性 · \(T\) 趋势 · \(P\) 重复/宣传/资源不匹配惩罚  

学习目标：

\[
P(\mathrm{useful}\mid x)=\sigma(\theta^\top x)
\]

每月输出权重敏感性：Top5 是否稳定；哪些篇仅在某权重进榜。

### 7.3 Daily limits（默认）

```yaml
daily_limits:
  initial_candidates: 200
  llm_screened: 30
  fulltext_analyzed: 5
  featured_papers: 3
  new_ideas: 1
  action_items: 3
exploration_mix:
  project_related: 0.70
  adjacent_methods: 0.20
  high_uncertainty: 0.10
```

### 7.4 领域分析模板（抽取字段）

**AI 论文**：真实差异、新机制、训练/推理预算、对照公平性、消融、闭源依赖、代码数据可用性。

**数学论文**：对象与定义、主定理与全部假设、结论类型（分类/界/存在/构造）、证明机制、依赖已知定理、是否计算验证、与当前证明的可迁移技巧。

**AI for Math**：竞赛/形式化/开放研究；可验证奖励；正确性检查；Lean/Isabelle/Coq；增益来自机制还是搜索预算；是否研究级；失败样例；工作流可迁移价值。

---

## 8. 组会 I/O 契约

### 8.1 角色输出（均须 schema 校验）

| 阶段 | 角色 | 关键输出 |
|------|------|----------|
| A | Scout | 新信号列表；相对昨日/7d/30d；异常主题 |
| B | Historian | 前作 TopK；脉络；增量类型；新颖性核对 |
| C | Analyst | 机制；必要部分 vs 实现细节 |
| D | Skeptic | 攻击点列表；evidence_against；「证据不足」允许 |
| E | Liaison | 影响的 project_id / question_id；支持或削弱 |
| F | Ideator | ≤1 idea；可 `skip` |
| G | Chair | 决议枚举；≤3 actions；State patch |

### 8.2 Decision schema

```yaml
decision:
  object_id: string
  verdict: READ | TRY | WATCH | ARCHIVE | NO-GO | UPDATE
  confidence: float
  rationale: [string]
  revisit_when: [string]
  actions: [string]          # max 3
  claim_ids: [CLM-...]
```

### 8.3 Idea schema

```yaml
idea:
  idea_id: IDEA-...
  title: string
  stage: signal | hypothesis | candidate | validated_candidate | active_project | rejected
  derived_from: { papers: [], questions: [], observations: [] }
  claim: string
  difference_from_prior_work: string
  minimum_test: string
  kill_criteria: [string]
  feasibility: { compute: low|medium|high, data: ..., theory: ... }
  max_contribution: string
  easiest_failure: string
```

Rejected 必须含：时间、原因、证据、复活条件。

---

## 9. 报告生成

### 9.1 单一内容管线

```text
CouncilResult JSON
  → Jinja2 渲染 Markdown（事实源，入 Git）
  → Jinja2 渲染自包含 HTML（KaTeX CDN + `templates/styles/tokens.css`，遵循 UI 设计系统）
  → （周会）python-pptx 生成 PPTX + 保留 Markdown 纪要
```

视觉规范见 [`05-ui-design.md`](./05-ui-design.md)。不依赖 Quarto / Node。路径：

```text
reports/daily/YYYY-MM-DD.md
reports/weekly/YYYY-Www.md
reports/monthly/YYYY-MM.md
reports/topic/<slug>.md
```

### 9.2 日报必选栏目

1. 头版结论（≤3）  
2. Research State Changes（可显式无变化）  
3. 今日精读  
4. 弱信号雷达  
5. Idea Watchlist  
6. 今日动作（≤3）  
7. 附录：候选、评分、抓取失败、模型/Prompt 版本、token 成本、证据引用  

### 9.3 新颖性允许输出（枚举）

```text
未发现高度相似工作
发现相似机制但应用对象不同
发现相同问题但评价协议不同
已有工作基本覆盖该想法
证据不足，不能判断
```

---

## 10. 反馈与学习

### 10.1 反馈枚举

```text
值得精读 | 与当前项目直接相关 | 方法可迁移 | 只是一般背景
证据不足 | 宣传大于贡献 | 资源不适配 | 已经看过 | 持续跟踪 | 不再推荐
```

只追加 `feedback.jsonl`，**不得改写历史报告**。  
「无点击 ≠ 不感兴趣」。

高影响配置变更（核心研究目标、死亡条件）须用户确认后写入。

### 10.2 可学习对象

兴趣/项目相关性、作者主题偏好、重复惩罚、Agent 错判统计、Idea 存活。

---

## 11. Run 级成本与复现日志

每次执行写入：

```yaml
run:
  run_id: string
  git_commit: string
  started_at: datetime
  finished_at: datetime
  mode: daily_lite | daily_deep | weekly | monthly | topic
  model_versions: object
  prompt_versions: object
  source_cursors: object
  input_tokens: int
  output_tokens: int
  total_cost_usd: float
  status: success | partial | failed
  failures: [string]
```

---

## 12. 模型路由

```text
规则 / 本地小模型：去重、分类、关键词、格式检查
低成本模型：结构化摘要、标签、初相关
强推理模型：定位、审稿、关联、Idea、Chair
可选独立模型：高风险结论交叉审查
数学深度分析：可用最强推理模型，但受 daily fulltext 上限约束
```

---

## 13. 评测规格（实现侧）

| 类别 | 指标 |
|------|------|
| 检索 | Recall@K, Precision@5, NDCG@10, Duplicate Rate, Missed Paper Audit |
| 可信 | Citation Coverage, Unsupported Claim Rate, Attribution Accuracy |
| 研究价值 | Actionability, Idea Survival Rate, NO-GO Value, Decision Change Precision |
| 个性化 | 反馈后排序改善、拒方向复发率、约束遵守 |
| 成本 | 单次 run 成本分布、强模型调用次数 |

离线集建议：100–200 篇人工标注（强/弱/无关/重复/值得精读/可迁移）。

---

## 14. 安全与合规

- 不绕过付费墙；不在公开站点再分发无授权全文  
- 密钥仅环境变量 / Actions secrets  
- 私有 `research_state` 默认不推送公开 Pages（或脱敏发布）  
- Prompt / 报告中的用户约束变更需确认  

---

## 15. MVP 实现顺序（工程）

1. ingest + normalize + dedupe + SQLite  
2. research_state 配置 + 两阶段 rank + daily md/html  
3. evidence + claim ledger + skeptic/liaison + state changes  
4. idea lifecycle + weekly + 反馈学习  
5. （可选）最小验证协议执行器  

接口与字段以本文件为准；产品意图冲突时回指 `01` / `02`。
