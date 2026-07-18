# Changelog

本文件记录**用户可见**行为变化。格式参考 Keep a Changelog。

## [Unreleased]

### Added

- P3 想法锦标赛：`council/tournament.py`（Skeptic + Feasibility 双维度 LLM 评估，自动晋升）
- `arc council tournament` CLI 命令（`--echo/--no-echo` 离线/在线模式，`--dry-run` 预览）
- 状态机自动路径：signal→hypothesis→candidate→validated_candidate（自动走完中间阶段）
- P3 Idea 生命周期：`ideas.jsonl` append-only，write/list/transition（含状态机验证）
- `arc idea add|list|transition` CLI 命令
- 周会 PPTX 生成：`python-pptx`，`arc weekly --pptx`（深色主题标题页 + 概览 + 任务）
- P2 验收：用 DeepSeek 对 3 篇论文运行完整 Council pipeline（Evidence/Skeptic/Historian/Liaison/Chair）
- P2 证据系统：`EvidenceType` 枚举 + PaperStore evidence 表（SQLite CRUD）
- Evidence Pack Builder：LLM 从论文摘要抽取结构化证据（定理/实验/主张/限制）
- Claim Ledger：`claims.jsonl` append-only，write/list/approve（Chair 审批门禁）
- 虚拟组会角色：Skeptic（批判评审）、Historian（前作检索+新颖性）、Liaison（项目映射）、Chair（决策+≤3 动作）
- `arc evidence build` / `arc claim add|list|approve` / `arc council review` CLI 命令
- `arc weekly` 周报骨架命令 + `templates/weekly/report.md.j2` 模板
- EchoModelProvider 新增 5 个 schema fixtures（Evidence/Skeptic/Historian/Liaison/Chair）
- 反馈系统：`FeedbackEntry` schema + `arc feedback add/list` CLI + append-only JSONL 存储
- 全链路 smoke：`arc smoke` 覆盖 config/store/normalize/rank/evidence/council/feedback/report 9 个步骤
- 日报真实数据接入：`build_daily_context`（ScreeningReport → 模板上下文）
- 全链路管线：`run_daily_full`（ingest → normalize → screen → report）
- `arc daily --no-skeleton` 全链路模式 + `--all` 强制重抓
- HTML 模板新增「今日精读 / 弱信号雷达」栏目
- arXiv 客户端：自动重试（指数退避，应对 429/5xx）
- 归一化管线：title_fingerprint dedup、check_dedup、run_normalization（metadata_only → NORMALIZED）
- 两阶段筛选：Stage 1 硬过滤（category/topic/negative keywords） + Stage 2 LLM 多维评分 + composite_score 排名
- `arc ingest normalize` / `arc ingest screen` CLI 命令
- 管线 `run_normalize_step` / `run_screening_step` 函数
- 测试：normalization dedup、hard filter、composite score
- arXiv 增量抓取客户端：按分类查询 arXiv API，Atom XML 解析，增量游标
- SQLite 持久层：PaperStore（papers 表 + source_cursors 表），支持 upsert/查询/游标管理
- `arc ingest arxiv` / `arc ingest status` CLI 命令
- 管线 `run_ingest_step` 异步函数
- 测试：PaperStore CRUD、arXiv XML 解析、parse→store 集成
- 项目骨架：`src/arc`、`config/`、`research_state/` 示例、Jinja2 日报模板、`arc` CLI
- UI 设计系统（Claude 暖色编辑风）[`docs/product/05-ui-design.md`](docs/product/05-ui-design.md)

### Changed

- `arc/normalization/__init__.py`：从 stub 升级为完整管线（dedup/指纹/状态转换）
- `arc/ranking/__init__.py`：从单一 composite_score 扩展为完整两阶段筛选
- `arc/config.py`：新增 `load_topics_config()`

### Fixed

- 本仓库补齐 local `user.name` / `user.email`（与其它仓一致；本机无全局 `.gitconfig`）

## [0.0.1] — 2026-07-18

### Added

- 产品文档四件套（`docs/product/`）
- 协作文档体系（`docs/collab/`、`AGENTS.md`、任务板等）
- [ADR-0002](docs/collab/adr/0002-stack-revision.md)：技术栈修订

### Changed

- 默认栈：去 Quarto / FAISS / LiteLLM / PptxGenJS 硬依赖；改为 Jinja2 HTML、NumPy 向量、openai-compatible、python-pptx、本机调度为主
