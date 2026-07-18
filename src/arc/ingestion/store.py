"""SQLite persistence for papers and source cursors.

Schema follows Tech Spec §5 (Paper entity) and §4 (source tracking).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from arc.schemas import Paper

DB_FILENAME = "arc.db"


class PaperStore:
    """Single-writer paper storage backed by SQLite.

    Thread-safe for reads; concurrent writes not guarded (single-process
    pipeline assumed for MVP).
    """

    def __init__(self, db_dir: str | Path) -> None:
        self.db_path = Path(db_dir) / DB_FILENAME
        self._conn: sqlite3.Connection | None = None

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._init_tables()
        return self._conn

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_tables(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS papers (
                canonical_id    TEXT PRIMARY KEY,
                doi             TEXT,
                arxiv_id        TEXT,
                openreview_id   TEXT,
                semantic_scholar_id TEXT,
                openalex_id     TEXT,
                title           TEXT NOT NULL,
                authors         TEXT NOT NULL DEFAULT '[]',
                categories      TEXT NOT NULL DEFAULT '[]',
                abstract        TEXT NOT NULL DEFAULT '',
                pdf_url         TEXT,
                source_url      TEXT,
                code_urls       TEXT NOT NULL DEFAULT '[]',
                versions        TEXT NOT NULL DEFAULT '[]',
                related_projects TEXT NOT NULL DEFAULT '[]',
                processing_status TEXT NOT NULL DEFAULT 'metadata_only',
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_papers_arxiv_id
                ON papers(arxiv_id);
            CREATE INDEX IF NOT EXISTS idx_papers_doi
                ON papers(doi);
            CREATE INDEX IF NOT EXISTS idx_papers_status
                ON papers(processing_status);
            CREATE INDEX IF NOT EXISTS idx_papers_source_url
                ON papers(source_url);

            CREATE TABLE IF NOT EXISTS source_cursors (
                source       TEXT PRIMARY KEY,
                cursor_value TEXT NOT NULL,
                fetched_at   TEXT NOT NULL
            );
        """)

    # ------------------------------------------------------------------
    # Paper CRUD
    # ------------------------------------------------------------------

    def upsert_paper(self, paper: Paper) -> str:
        """Insert or update a paper by canonical_id. Returns the id."""
        now = datetime.now(timezone.utc).isoformat()
        row = self._paper_to_row(paper, now)

        c = self.conn
        existing = c.execute(
            "SELECT created_at FROM papers WHERE canonical_id = ?",
            (paper.canonical_id,),
        ).fetchone()
        if existing:
            row["created_at"] = existing["created_at"]

        c.execute(
            """INSERT INTO papers (
                canonical_id, doi, arxiv_id,
                openreview_id, semantic_scholar_id, openalex_id,
                title, authors, categories, abstract,
                pdf_url, source_url, code_urls,
                versions, related_projects, processing_status,
                created_at, updated_at
            ) VALUES (
                :canonical_id, :doi, :arxiv_id,
                :openreview_id, :semantic_scholar_id, :openalex_id,
                :title, :authors, :categories, :abstract,
                :pdf_url, :source_url, :code_urls,
                :versions, :related_projects, :processing_status,
                :created_at, :updated_at
            ) ON CONFLICT(canonical_id) DO UPDATE SET
                doi             = excluded.doi,
                arxiv_id        = excluded.arxiv_id,
                openreview_id   = excluded.openreview_id,
                semantic_scholar_id = excluded.semantic_scholar_id,
                openalex_id     = excluded.openalex_id,
                title           = excluded.title,
                authors         = excluded.authors,
                categories      = excluded.categories,
                abstract        = excluded.abstract,
                pdf_url         = excluded.pdf_url,
                source_url      = excluded.source_url,
                code_urls       = excluded.code_urls,
                versions        = excluded.versions,
                related_projects = excluded.related_projects,
                processing_status = excluded.processing_status,
                updated_at      = excluded.updated_at
            """,
            row,
        )
        self.conn.commit()
        return paper.canonical_id

    def get_paper(self, canonical_id: str) -> Paper | None:
        row = self.conn.execute(
            "SELECT * FROM papers WHERE canonical_id = ?",
            (canonical_id,),
        ).fetchone()
        return self._row_to_paper(row) if row else None

    def get_paper_by_arxiv(self, arxiv_id: str) -> Paper | None:
        row = self.conn.execute(
            "SELECT * FROM papers WHERE arxiv_id = ?",
            (arxiv_id,),
        ).fetchone()
        return self._row_to_paper(row) if row else None

    def get_papers(
        self,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Paper]:
        if status:
            rows = self.conn.execute(
                "SELECT * FROM papers WHERE processing_status = ?"
                " ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                (status, limit, offset),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM papers ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [self._row_to_paper(r) for r in rows]

    def count_papers(self, status: str | None = None) -> int:
        if status:
            row = self.conn.execute(
                "SELECT COUNT(*) AS cnt FROM papers WHERE processing_status = ?",
                (status,),
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT COUNT(*) AS cnt FROM papers"
            ).fetchone()
        return row["cnt"] if row else 0

    # ------------------------------------------------------------------
    # Source cursors (incremental fetch tracking)
    # ------------------------------------------------------------------

    def get_cursor(self, source: str) -> str | None:
        row = self.conn.execute(
            "SELECT cursor_value FROM source_cursors WHERE source = ?",
            (source,),
        ).fetchone()
        return row["cursor_value"] if row else None

    def set_cursor(self, source: str, cursor_value: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """INSERT INTO source_cursors (source, cursor_value, fetched_at)
               VALUES (?, ?, ?)
               ON CONFLICT(source) DO UPDATE SET
                   cursor_value = excluded.cursor_value,
                   fetched_at   = excluded.fetched_at""",
            (source, cursor_value, now),
        )
        self.conn.commit()

    def list_cursors(self) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT source, cursor_value, fetched_at FROM source_cursors"
            " ORDER BY source"
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def _paper_to_row(self, paper: Paper, now: str) -> dict[str, Any]:
        return {
            "canonical_id": paper.canonical_id,
            "doi": paper.doi,
            "arxiv_id": paper.arxiv_id,
            "openreview_id": paper.openreview_id,
            "semantic_scholar_id": paper.semantic_scholar_id,
            "openalex_id": paper.openalex_id,
            "title": paper.title,
            "authors": json.dumps(paper.authors, ensure_ascii=False),
            "categories": json.dumps(paper.categories, ensure_ascii=False),
            "abstract": paper.abstract,
            "pdf_url": paper.pdf_url,
            "source_url": paper.source_url,
            "code_urls": json.dumps(paper.code_urls, ensure_ascii=False),
            "versions": json.dumps(paper.versions, ensure_ascii=False),
            "related_projects": json.dumps(paper.related_projects, ensure_ascii=False),
            "processing_status": paper.processing_status,
            "created_at": now,
            "updated_at": now,
        }

    def _row_to_paper(self, row: sqlite3.Row) -> Paper:
        return Paper(
            canonical_id=row["canonical_id"],
            doi=row["doi"],
            arxiv_id=row["arxiv_id"],
            openreview_id=row["openreview_id"],
            semantic_scholar_id=row["semantic_scholar_id"],
            openalex_id=row["openalex_id"],
            title=row["title"],
            authors=json.loads(row["authors"]),
            categories=json.loads(row["categories"]),
            abstract=row["abstract"],
            pdf_url=row["pdf_url"],
            source_url=row["source_url"],
            code_urls=json.loads(row["code_urls"]),
            versions=json.loads(row["versions"]),
            related_projects=json.loads(row["related_projects"]),
            processing_status=row["processing_status"],
        )
