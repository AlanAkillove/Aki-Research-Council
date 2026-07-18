# Changelog

本文件记录**用户可见**行为变化。格式参考 Keep a Changelog。

## [Unreleased]

### Added

- （尚无运行时行为）

### Changed

- （尚无）

### Fixed

- （尚无）

## [0.0.1] — 2026-07-18

### Added

- 产品文档四件套（`docs/product/`）
- 协作文档体系（`docs/collab/`、`AGENTS.md`、任务板等）
- [ADR-0002](docs/collab/adr/0002-stack-revision.md)：技术栈修订

### Changed

- 默认栈：去 Quarto / FAISS / LiteLLM / PptxGenJS 硬依赖；改为 Jinja2 HTML、NumPy 向量、openai-compatible、python-pptx、本机调度为主
