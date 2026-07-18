"""SQLite persistence for papers and source cursors.

Schema follows Tech Spec §5 (Paper entity) and §4 (source tracking).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from arc.schemas import Paper, Evidence, EvidenceType, SourceTier

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

            CREATE TABLE IF NOT EXISTS evidence (
                id               TEXT PRIMARY KEY,
                paper_id         TEXT NOT NULL,
                content          TEXT NOT NULL,
                evidence_type    TEXT NOT NULL DEFAULT 'other',
                source_tier      TEXT NOT NULL DEFAULT 'A',
                extraction_method TEXT NOT NULL DEFAULT 'api',
                confidence       REAL NOT NULL DEFAULT 0.8,
                location         TEXT NOT NULL DEFAULT '{}',
                created_at       TEXT NOT NULL,
                FOREIGN KEY (paper_id) REFERENCES papers(canonical_id)
            );
            CREATE INDEX IF NOT EXISTS idx_evidence_paper
                ON evidence(paper_id);
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
    # Evidence CRUD
    # ------------------------------------------------------------------

    def upsert_evidence(self, evidence: Evidence) -> str:
        """Insert or update an evidence record. Returns evidence id."""
        now = datetime.now(timezone.utc).isoformat()
        row = {
            "id": evidence.id,
            "paper_id": evidence.paper_id,
            "content": evidence.content,
            "evidence_type": evidence.evidence_type.value,
            "source_tier": evidence.source_tier.value,
            "extraction_method": evidence.extraction_method,
            "confidence": evidence.confidence,
            "location": json.dumps(evidence.location, ensure_ascii=False),
            "created_at": now,
        }
        self.conn.execute(
            """INSERT INTO evidence (id, paper_id, content, evidence_type,
                source_tier, extraction_method, confidence, location, created_at)
               VALUES (:id, :paper_id, :content, :evidence_type,
                :source_tier, :extraction_method, :confidence, :location, :created_at)
               ON CONFLICT(id) DO UPDATE SET
                content = excluded.content,
                evidence_type = excluded.evidence_type,
                confidence = excluded.confidence,
                location = excluded.location""",
            row,
        )
        self.conn.commit()
        return evidence.id

    def get_evidence(self, evidence_id: str) -> Evidence | None:
        row = self.conn.execute(
            "SELECT * FROM evidence WHERE id = ?", (evidence_id,)
        ).fetchone()
        return self._row_to_evidence(row) if row else None

    def get_evidence_by_paper(self, paper_id: str) -> list[Evidence]:
        rows = self.conn.execute(
            "SELECT * FROM evidence WHERE paper_id = ? ORDER BY created_at",
            (paper_id,),
        ).fetchall()
        return [self._row_to_evidence(r) for r in rows]

    def count_evidence(self, paper_id: str | None = None) -> int:
        if paper_id:
            row = self.conn.execute(
                "SELECT COUNT(*) AS cnt FROM evidence WHERE paper_id = ?",
                (paper_id,),
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT COUNT(*) AS cnt FROM evidence"
            ).fetchone()
        return row["cnt"] if row else 0

    def _row_to_evidence(self, row: sqlite3.Row) -> Evidence:
        return Evidence(
            id=row["id"],
            paper_id=row["paper_id"],
            content=row["content"],
            evidence_type=EvidenceType(row["evidence_type"]),
            source_tier=SourceTier(row["source_tier"]),
            extraction_method=row["extraction_method"],
            confidence=row["confidence"],
            location=json.loads(row["location"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

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
