"""Tests for ingestion: PaperStore SQLite and arXiv XML parsing."""

from __future__ import annotations

import json
from pathlib import Path

from arc.ingestion import ArxivClient, PaperStore
from arc.schemas import Paper


# ---------------------------------------------------------------------------
# PaperStore
# ---------------------------------------------------------------------------


def test_store_create_db(tmp_path: Path) -> None:
    store = PaperStore(tmp_path)
    assert store.db_path == tmp_path / "arc.db"
    assert store.conn is not None
    store.close()
    assert store.db_path.exists()


def test_store_upsert_and_get(tmp_path: Path) -> None:
    store = PaperStore(tmp_path)
    paper = Paper(
        canonical_id="arxiv:2607.12345",
        arxiv_id="2607.12345",
        title="Test Paper Title",
        authors=["Alice", "Bob"],
        categories=["cs.AI", "cs.LG"],
        abstract="This is a test abstract.",
    )
    cid = store.upsert_paper(paper)
    assert cid == "arxiv:2607.12345"

    fetched = store.get_paper("arxiv:2607.12345")
    assert fetched is not None
    assert fetched.title == "Test Paper Title"
    assert fetched.authors == ["Alice", "Bob"]
    assert fetched.categories == ["cs.AI", "cs.LG"]
    assert fetched.abstract == "This is a test abstract."

    store.close()


def test_store_upsert_update(tmp_path: Path) -> None:
    store = PaperStore(tmp_path)

    p1 = Paper(
        canonical_id="arxiv:2607.99999",
        arxiv_id="2607.99999",
        title="Original Title",
        authors=["A"],
        categories=["cs.AI"],
        versions=["v1"],
    )
    store.upsert_paper(p1)

    p2 = Paper(
        canonical_id="arxiv:2607.99999",
        arxiv_id="2607.99999",
        title="Updated Title",
        authors=["A", "B"],
        categories=["cs.AI", "cs.LG"],
        versions=["v1", "v2"],
    )
    store.upsert_paper(p2)

    fetched = store.get_paper("arxiv:2607.99999")
    assert fetched is not None
    assert fetched.title == "Updated Title"
    assert fetched.authors == ["A", "B"]
    assert fetched.versions == ["v1", "v2"]

    # created_at should be stable
    assert fetched.canonical_id == "arxiv:2607.99999"

    store.close()


def test_store_get_paper_by_arxiv(tmp_path: Path) -> None:
    store = PaperStore(tmp_path)
    paper = Paper(
        canonical_id="arxiv:2607.55555",
        arxiv_id="2607.55555",
        title="By arXiv ID",
        authors=[],
        categories=[],
    )
    store.upsert_paper(paper)

    fetched = store.get_paper_by_arxiv("2607.55555")
    assert fetched is not None
    assert fetched.title == "By arXiv ID"

    missing = store.get_paper_by_arxiv("9999.99999")
    assert missing is None

    store.close()


def test_store_cursors(tmp_path: Path) -> None:
    store = PaperStore(tmp_path)
    assert store.get_cursor("arxiv:cs.AI") is None

    store.set_cursor("arxiv:cs.AI", "2607.00100")
    assert store.get_cursor("arxiv:cs.AI") == "2607.00100"

    store.set_cursor("arxiv:cs.AI", "2607.00200")
    assert store.get_cursor("arxiv:cs.AI") == "2607.00200"

    cursors = store.list_cursors()
    assert len(cursors) == 1
    assert cursors[0]["source"] == "arxiv:cs.AI"

    store.close()


def test_store_count(tmp_path: Path) -> None:
    store = PaperStore(tmp_path)
    assert store.count_papers() == 0

    for i in range(5):
        p = Paper(
            canonical_id=f"arxiv:2607.{10000 + i}",
            arxiv_id=f"2607.{10000 + i}",
            title=f"Paper {i}",
            authors=[],
            categories=[],
            processing_status="metadata_only",
        )
        store.upsert_paper(p)

    assert store.count_papers() == 5
    assert store.count_papers("metadata_only") == 5
    assert store.count_papers("screened") == 0

    papers = store.get_papers(limit=3)
    assert len(papers) == 3

    store.close()


# ---------------------------------------------------------------------------
# arXiv XML parsing
# ---------------------------------------------------------------------------


SAMPLE_ARXIV_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2607.12345v1</id>
    <updated>2026-07-17T18:30:00Z</updated>
    <published>2026-07-17T18:30:00Z</published>
    <title> A Novel Method for Mathematical Reasoning </title>
    <summary>
      We present a novel approach to mathematical reasoning using
      transformer-based architectures. Our method achieves state-of-the-art
      results on the MATH benchmark.
    </summary>
    <author>
      <name>John Smith</name>
    </author>
    <author>
      <name>Jane Doe</name>
    </author>
    <arxiv:primary_category term="cs.AI" />
    <category term="cs.AI" />
    <category term="cs.LG" />
    <link href="http://arxiv.org/abs/2607.12345v1" rel="alternate" type="text/html" />
    <link href="http://arxiv.org/pdf/2607.12345v1" rel="related" type="application/pdf" title="pdf" />
  </entry>
</feed>
"""


def test_arxiv_parse_entries() -> None:
    """Verify ArxivClient._parse_entries extracts fields correctly."""
    store = PaperStore(Path("/tmp/nonexistent"))  # not used for parsing
    client = ArxivClient(store)
    entries = client._parse_entries(SAMPLE_ARXIV_XML)
    assert len(entries) == 1

    e = entries[0]
    assert e["arxiv_id"] == "2607.12345v1"
    assert e["base_arxiv_id"] == "2607.12345"
    assert e["version"] == "v1"
    assert e["title"] == "A Novel Method for Mathematical Reasoning"
    assert "mathematical" in e["abstract"]
    assert e["authors"] == ["John Smith", "Jane Doe"]
    assert e["categories"] == ["cs.AI", "cs.LG"]
    assert e["abs_url"] == "http://arxiv.org/abs/2607.12345v1"
    assert e["pdf_url"] == "http://arxiv.org/pdf/2607.12345v1"
    assert e["published"] == "2026-07-17T18:30:00Z"


MULTI_ENTRY_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2607.11111v1</id>
    <published>2026-07-18T10:00:00Z</published>
    <title>First Paper</title>
    <summary>Abstract one.</summary>
    <author><name>Alice</name></author>
    <arxiv:primary_category term="cs.CV" />
    <category term="cs.CV" />
    <link href="http://arxiv.org/abs/2607.11111v1" rel="alternate" />
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2607.22222v2</id>
    <published>2026-07-18T11:00:00Z</published>
    <title>Second Paper</title>
    <summary>Abstract two.</summary>
    <author><name>Bob</name></author>
    <arxiv:primary_category term="math.CO" />
    <category term="math.CO" />
    <link href="http://arxiv.org/abs/2607.22222v2" rel="alternate" />
    <link href="http://arxiv.org/pdf/2607.22222v2" title="pdf" rel="related" />
  </entry>
</feed>
"""


def test_arxiv_parse_multi_entry() -> None:
    store = PaperStore(Path("/tmp/nonexistent"))
    client = ArxivClient(store)
    entries = client._parse_entries(MULTI_ENTRY_XML)
    assert len(entries) == 2
    assert entries[0]["title"] == "First Paper"
    assert entries[1]["title"] == "Second Paper"
    assert entries[0]["categories"] == ["cs.CV"]
    assert entries[1]["categories"] == ["math.CO"]
    assert entries[1]["base_arxiv_id"] == "2607.22222"


# ---------------------------------------------------------------------------
# Integration: parse & store round-trip
# ---------------------------------------------------------------------------


def test_parse_and_store(tmp_path: Path) -> None:
    store = PaperStore(tmp_path)
    client = ArxivClient(store)
    entries = client._parse_entries(SAMPLE_ARXIV_XML)
    assert len(entries) == 1

    raw = entries[0]
    from arc.normalization import pick_canonical_id

    paper = Paper(
        canonical_id=pick_canonical_id(arxiv_id=raw["base_arxiv_id"]),
        arxiv_id=raw["base_arxiv_id"],
        title=raw["title"],
        authors=raw["authors"],
        categories=raw["categories"],
        abstract=raw["abstract"],
        pdf_url=raw["pdf_url"] or None,
        source_url=raw["abs_url"] or None,
        versions=[raw["version"]],
    )
    store.upsert_paper(paper)

    fetched = store.get_paper("arxiv:2607.12345")
    assert fetched is not None
    assert fetched.title == "A Novel Method for Mathematical Reasoning"
    assert fetched.authors == ["John Smith", "Jane Doe"]
    assert fetched.categories == ["cs.AI", "cs.LG"]
    assert fetched.versions == ["v1"]

    store.close()
