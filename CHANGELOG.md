# Changelog

本文件记录**用户可见**行为变化。格式参考 Keep a Changelog。

## [Unreleased]

### Added

- arXiv 增量抓取客户端：按分类查询 arXiv API，Atom XML 解析，增量游标
- SQLite 持久层：PaperStore（papers 表 + source_cursors 表），支持 upsert/查询/游标管理
- `arc ingest arxiv` / `arc ingest status` CLI 命令
- 管线 `run_ingest_step` 异步函数
- 测试：PaperStore CRUD、arXiv XML 解析、parse→store 集成
- 项目骨架：`src/arc`、`config/`、`research_state/` 示例、Jinja2 日报模板、`arc` CLI
- UI 设计系统（Claude 暖色编辑风）[`docs/product/05-ui-design.md`](docs/product/05-ui-design.md)

### Changed

- `arc/ingestion/__init__.py`：从 stub 替换为实际导出（ArxivClient, PaperStore）

### Fixed

- 本仓库补齐 local `user.name` / `user.email`（与其它仓一致；本机无全局 `.gitconfig`）

## [0.0.1] — 2026-07-18

### Added

- 产品文档四件套（`docs/product/`）
- 协作文档体系（`docs/collab/`、`AGENTS.md`、任务板等）
- [ADR-0002](docs/collab/adr/0002-stack-revision.md)：技术栈修订

### Changed

- 默认栈：去 Quarto / FAISS / LiteLLM / PptxGenJS 硬依赖；改为 Jinja2 HTML、NumPy 向量、openai-compatible、python-pptx、本机调度为主
