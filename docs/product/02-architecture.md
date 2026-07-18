# ARC 架构 / 方案（Architecture）

> **对应产品原则**：[`01-prd-summary.md`](./01-prd-summary.md)  
> **实现细节**：[`03-tech-spec.md`](./03-tech-spec.md)  
> **版本**：v0.3

---

## 1. 架构决策（一句话）

> **单一研究状态中心 + 并行信息侦察 + 证据级检索 + 少量角色化评审 + 串行主席决策 + 多格式发布。**

不采用「Agent 越多越高级」。可并行：采集、检索、独立审稿；必须串行：最终论证、状态写入、研究计划。

---

## 2. 七层结构

```text
┌───────────────────────────────────────────────┐
│ 7. 发布与交互：HTML / Markdown / PPT / 反馈   │
├───────────────────────────────────────────────┤
│ 6. 决策层：Chair · GO/WATCH/NO-GO · 任务      │
├───────────────────────────────────────────────┤
│ 5. 虚拟组会：定位、审稿、关联、想法           │
├───────────────────────────────────────────────┤
│ 4. 证据层：全文片段、定理、实验、引用与反证   │
├───────────────────────────────────────────────┤
│ 3. 筛选层：硬过滤、向量召回、图推荐、LLM 精排 │
├───────────────────────────────────────────────┤
│ 2. 文献知识层：去重、实体对齐、论文图、趋势   │
├───────────────────────────────────────────────┤
│ 1. 数据采集层：arXiv / OpenReview / API 等    │
└───────────────────────────────────────────────┘
                 ↕ 持续读写
┌───────────────────────────────────────────────┐
│ Research State（中心事实源）                  │
│ 项目 · 问题 · Claim · Idea · 决策 · 反馈      │
└───────────────────────────────────────────────┘
```

**Research State 不是普通向量库**：所有 Agent 只能围绕它工作；**仅 Chair 可修改正式状态**。

---

## 3. 对现有系统的吸收与取舍

### 3.1 吸收

| 来源 | 吸收点 |
|------|--------|
| STORM / Co-STORM | 先扩展问题再搜证据；主持人暴露未讨论问题；动态概念结构 |
| PaperQA2 | 问题→检索→证据片段→主张→引用；矛盾检测思路 |
| OpenScholar / Asta | 有依据综合；成本与受控工具环境理念 |
| Google AI co-scientist | 想法锦标赛（**仅周会**，非每日） |
| zotero-arxiv-daily 等 | 采集、个性化、Actions 发布 |
| agents-radar | 多源调度、去重、日/周报、Pages |

### 3.2 明确不采用

- 每日对所有论文做昂贵多轮自博弈
- 语言模型自由宣称「首个 / 创新性」（须检索限定表述）
- 第一阶段复制 AI Scientist 的自动实验与自动写论文
- 无证据 / 无差异 / 无死亡条件的点子写入正式方向

### 3.3 从 PRC 草案并入的架构补强

- 论文**版本归一与差分**（同一工作新版本 ≠ 新论文）
- 推荐**多样性约束**与 **70/20/10 探索配比**
- AI / 数学 / AI-for-Math **差异化分析模板**
- **月度回顾**与 run 级成本 / 复现日志
- 组会 **A→G 固定状态机**（非自由群聊）

---

## 4. 数据源策略

### 4.1 一级（可支撑学术判断）

- **arXiv**：每日召回；数学优先 TeX 源码
- **OpenReview**：投稿、公开评审、作者回复、争议（主张与质疑同进证据包）
- **Semantic Scholar**：引用图、相似推荐、正负种子推荐
- **OpenAlex**：主题层级、机构、趋势
- **Crossref + Unpaywall**：DOI / 出版对齐；合法 OA；不绕过付费墙

### 4.2 二级（信号，不能单独支撑数学结论）

GitHub、实验室博客、Hugging Face、会议页、作者主页——用于开源、复现、社区问题、升温信号。

### 4.3 来源可信度

| 等级 | 含义 |
|------|------|
| A | 正文/附录、正式审稿、官方代码与数据 |
| B | 作者项目页、官方研究博客、会议页 |
| C | GitHub issue、社区讨论、独立复现 |
| D | 新闻转载、社交媒体、无来源评论 |

重要判断必须标注主要依据等级。

### 4.4 用户私有上下文

Zotero / 当前 TeX / README / 实验报告 / 笔记 / Idea backlog / 组会决议 / 研究配置 =「我在做什么」；公共源 =「外界发生了什么」。

---

## 5. Research State 概念模型

### 5.1 目录意象

```text
research_state/
├── researcher_profile.yaml
├── projects/
├── questions.yaml
├── claims.jsonl          # Claim Ledger
├── ideas.jsonl
├── decisions.jsonl
├── reading_events.jsonl
├── feedback.jsonl
├── paper_graph.sqlite
├── evidence_index/
├── reports/
└── meeting_minutes/
```

### 5.2 关键对象

- **Project**：核心问题、假设、约束、已知失败、死亡条件
- **Open Question**：归属项目、blocking、正反证据列表
- **Idea**：生命周期 + 最小验证 + kill criteria（见下）
- **Claim**：类型化主张 + 证据编号 + 批准者（Chair）
- **Decision**：GO / WATCH / NO-GO / READ / TRY / ARCHIVE / UPDATE + 复访条件

### 5.3 Idea 生命周期

```text
signal → hypothesis → candidate → validated_candidate → active_project
任意阶段 → rejected（保留理由与复活条件，禁止删除）
```

每日最多产生 **1** 个新 hypothesis；不足证据时不生成。

---

## 6. 筛选漏斗与探索配比

```text
~200 元数据召回
→ 硬过滤 / 去重 / 已读已拒
→ ~30 LLM 结构化精排
→ ≤5 全文分析
→ ≤3 头版 / 精读
```

**探索配比（可配置）**：

- 70% 当前项目相关
- 20% 邻近方法
- 10% 高不确定探索

**多样性**：头版严格按研究价值；雷达强调主题覆盖；附录保留完整候选。同主题垄断前十时用 MMR / 聚类约束，但多样性不得压过相关性。

**权重**：初始保守先验；用反馈学习「值得精读」概率；每月做权重敏感性分析（非永久拍脑袋常数）。

---

## 7. 虚拟组会角色（职责，非必须七进程）

| 角色 | 职责 |
|------|------|
| Scout | 候选与信号；分 AI / Math / Project / Ecosystem；不给最终评价 |
| Evidence Builder | 建 Evidence Pack；后续引用必须指向证据编号 |
| Historian | 前作、脉络、真实增量、新颖性 vs 检索 |
| Skeptic | 固定检查清单；可说「证据不足」，禁止为辩论而硬反 |
| Liaison | 对齐 Research State：影响哪项目/问题/假设 |
| Ideator | 仅从证据链生成切口；含死亡条件与最大贡献 |
| **Chair** | **唯一**写正式状态；合并冲突；决议与任务 |

### 7.1 每日组会状态机（A→G）

```text
A Scout Brief
→ B Literature Positioning
→ C Mechanism Analysis
→ D Skeptical Review
→ E Project Connector
→ F Idea Generation（可跳过）
→ G Chair Decision
```

### 7.2 Chair 决议枚举

`READ` | `TRY` | `WATCH` | `ARCHIVE` | `NO-GO` | `UPDATE`  
并输出 ≤3 个下一步动作。

---

## 8. 三种工作流

### 8.1 每日研究晨报（8–15 分钟）

1. 头版结论（≤3）  
2. **Research State Changes**（最重要；可无变化）  
3. 今日精读（2–4）  
4. 弱信号雷达  
5. Idea Watchlist（状态变化优先）  
6. 今日动作（≤3）  
7. 附录：完整候选、评分、失败、成本、证据引用  

### 8.2 每周虚拟组会（主决策场景）

8–10 页：状态变化 → 分域趋势 → 深读 → 争议 → 项目连接 → **想法锦标赛（Generation / Skeptic / Feasibility）** → GO/WATCH/NO-GO → 下周任务。  
**每周至多 1 个方向进入「待验证」。**

### 8.3 专题研究会

用户指定问题 → 形式化 → 检索 → 路线图 → 共识/冲突 → 未解问题 → 候选建模 → 最小实验 → 死亡条件 → 备忘录（+ 可选 PPT）。

### 8.4 月度回顾（并入）

不逐篇：主题升温/消失、Idea 漏斗、精读命中、Agent 错判统计、组合是否过散、下月探索增减、成本收益。

---

## 9. 发布与调度架构

```text
结构化 JSON（单一逻辑事实）
  → Markdown（Git 可 diff 的内容事实源）
  → HTML（Jinja2 自包含页；公式 KaTeX）
  → PPTX（python-pptx；周会另保留 Markdown 纪要）
```

静态站点：归档、按项目过滤、证据折叠、反馈按钮、State 对照、Rejected Ideas。  
**Quarto / PptxGenJS 不在主路径**（见 [ADR-0002](../collab/adr/0002-stack-revision.md)）。

调度：

- **主路径**：本机定时或手动跑 council（长推理、私有 State、密钥）
- **辅路径**：GitHub Actions 做 CI、Pages、可选轻量 ingest 镜像
- 采集与分析分 workflow；失败可降级出 `partial` 报告

---

## 10. 可信性机制（架构层）

1. **Claim Ledger**：fact / author_claim / external_claim / inference / hypothesis / recommendation  
2. **新颖性五档输出**（禁止「这是全新的」）：未发现高度相似 / 相似机制异对象 / 同问题异评价 / 已被覆盖 / 证据不足  
3. **数学特殊规则**：精确量词与假设；禁有限实验推一般；证明缺失显式标记；TeX 优先  
4. **版本事件**：新版本触发生成差异报告，而非新论文条目  

---

## 11. 运行模式

| 模式 | 何时 | 深度 |
|------|------|------|
| Daily Lite | 每日 | 初筛 + 少量结构化分析 + 晨报 |
| Daily Deep | 高优先级信号 | 全文、引用链、Skeptic、State 更新 |
| Weekly Council | 每周 | 冲突、锦标赛、PPT |
| Topic Dive | 用户触发 | 递归问题分解，结果写回 State |
| Monthly Retro | 每月 | 漏斗与校准，非逐篇 |

---

## 12. 分阶段边界

| 阶段 | 架构焦点 |
|------|----------|
| 1 | 采集对齐 + 两阶段筛选 + 日报 + 基础反馈 |
| 2 | Evidence Pack + Historian/Skeptic/Liaison + Claim Ledger + State Changes |
| 3 | Idea 生命周期 + 决策 + 权重学习 + 周会 PPT |
| 4 | 最小验证助手与结果回写（仍不自动提交） |

技术选型、schema、仓库与状态机细节见 [`03-tech-spec.md`](./03-tech-spec.md)。
