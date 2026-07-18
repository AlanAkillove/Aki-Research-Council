"""arXiv API client for incremental paper fetching.

Uses the arXiv query API (export.arxiv.org) with Atom XML responses.
Deduplication is handled by PaperStore upsert; the client track cursors
per category for incremental fetching.

API docs: https://info.arxiv.org/help/api/
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Any
from xml.etree import ElementTree

import httpx

from arc.config import load_sources_config
from arc.ingestion.store import PaperStore
from arc.normalization import pick_canonical_id
from arc.schemas import Paper

logger = logging.getLogger(__name__)

ARXIV_API_URL = "https://export.arxiv.org/api/query"
ARXIV_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}
REQUEST_INTERVAL_S = 3.0  # seconds between requests per arXiv fair-use policy
ARXIV_ID_RE = re.compile(r"(\d{4}\.\d{4,5})(v\d+)?")


class ArxivClient:
    """Asynchronous client for the arXiv query API."""

    def __init__(
        self,
        store: PaperStore,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.store = store
        self.http = http_client or httpx.AsyncClient(timeout=30.0, follow_redirects=True)

    # ------------------------------------------------------------------
    # Fetch & parse
    # ------------------------------------------------------------------

    async def fetch_category(
        self,
        category: str,
        max_results: int = 200,
        max_retries: int = 3,
    ) -> list[dict[str, Any]]:
        """Fetch recent submissions for a single arXiv category.

        Retries with exponential backoff on 429 / 5xx.
        """
        params: dict[str, Any] = {
            "search_query": f"cat:{category}",
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "max_results": max_results,
        }
        last_error = ""
        for attempt in range(max_retries):
            try:
                logger.info(
                    "Fetching arXiv category=%s max_results=%d attempt=%d",
                    category, max_results, attempt + 1,
                )
                resp = await self.http.get(ARXIV_API_URL, params=params)
                resp.raise_for_status()
                return self._parse_entries(resp.text)
            except httpx.HTTPStatusError as exc:
                last_error = str(exc)
                status = exc.response.status_code
                if status in (429, 502, 503):
                    wait = 3.0 * (2 ** attempt)
                    logger.warning(
                        "arXiv %s for %s, retrying in %.0fs (attempt %d/%d)",
                        status, category, wait, attempt + 1, max_retries,
                    )
                    await asyncio.sleep(wait)
                else:
                    raise
        raise httpx.HTTPStatusError(
            f"arXiv {category} failed after {max_retries} retries: {last_error}",
            request=resp.request, response=resp,
        )

    def _parse_entries(self, xml_text: str) -> list[dict[str, Any]]:
        """Parse arXiv Atom XML into a list of raw entry dicts."""
        root = ElementTree.fromstring(xml_text)
        entries: list[dict[str, Any]] = []
        for entry_elem in root.findall("atom:entry", ARXIV_NS):
            entry = self._parse_entry(entry_elem)
            if entry is not None:
                entries.append(entry)
        return entries

    def _parse_entry(self, entry: ElementTree.Element) -> dict[str, Any] | None:
        """Parse a single Atom ``<entry>`` element."""
        id_text = self._text(entry.find("atom:id", ARXIV_NS)) or ""
        raw_title = self._text(entry.find("atom:title", ARXIV_NS)) or ""
        if not raw_title:
            return None

        raw_title = raw_title.strip()
        arxiv_id = self._extract_arxiv_id(id_text)
        if not arxiv_id:
            return None

        published_raw = self._text(entry.find("atom:published", ARXIV_NS)) or ""
        summary_raw = self._normalize_abstract(
            self._text(entry.find("atom:summary", ARXIV_NS)) or ""
        )

        authors: list[str] = []
        for author_el in entry.findall("atom:author", ARXIV_NS):
            name = self._text(author_el.find("atom:name", ARXIV_NS))
            if name:
                authors.append(name.strip())

        categories: list[str] = []
        for cat_el in entry.findall("atom:category", ARXIV_NS):
            term = cat_el.get("term")
            if term:
                categories.append(term)

        primary = entry.find("arxiv:primary_category", ARXIV_NS)
        if primary is not None:
            pt = primary.get("term")
            if pt and pt not in categories:
                categories.insert(0, pt)

        abs_url = ""
        pdf_url = ""
        for link in entry.findall("atom:link", ARXIV_NS):
            href = link.get("href", "")
            rel = link.get("rel", "")
            link_title = link.get("title", "")
            if rel == "alternate":
                abs_url = href
            elif link_title == "pdf":
                pdf_url = href

        m = ARXIV_ID_RE.match(arxiv_id)
        base_id = m.group(1) if m else arxiv_id
        version_str = (m.group(2) or "v1") if m else "v1"

        return {
            "arxiv_id": arxiv_id,
            "base_arxiv_id": base_id,
            "version": version_str,
            "title": raw_title,
            "abstract": summary_raw,
            "authors": authors,
            "categories": categories,
            "published": published_raw,
            "abs_url": abs_url,
            "pdf_url": pdf_url,
        }

    # ------------------------------------------------------------------
    # Ingestion pipeline
    # ------------------------------------------------------------------

    async def ingest_category(
        self,
        category: str,
        max_results: int = 200,
        force_all: bool = False,
    ) -> tuple[int, int]:
        """Fetch and store papers for a single arXiv category.

        Returns ``(newly_stored_count, total_fetched_count)``.
        """
        cursor_key = f"arxiv:{category}"
        cursor_value: str | None = None if force_all else self.store.get_cursor(cursor_key)
        raw_entries = await self.fetch_category(category, max_results=max_results)

        new_count = 0
        for raw in raw_entries:
            # Skip entries we already know about via cursor.
            if not force_all and cursor_value and raw["base_arxiv_id"] <= cursor_value:
                continue

            existing = self.store.get_paper_by_arxiv(raw["base_arxiv_id"])
            all_versions = [raw["version"]]
            if existing:
                all_versions = sorted(set(existing.versions + all_versions))

            canonical_id = pick_canonical_id(arxiv_id=raw["base_arxiv_id"])
            paper = Paper(
                canonical_id=canonical_id,
                arxiv_id=raw["base_arxiv_id"],
                title=raw["title"],
                authors=raw["authors"],
                categories=raw["categories"],
                abstract=raw["abstract"],
                pdf_url=raw["pdf_url"] or None,
                source_url=raw["abs_url"] or None,
                versions=all_versions,
            )
            self.store.upsert_paper(paper)
            new_count += 1

        # Advance cursor: the largest base arXiv ID in this batch.
        if raw_entries:
            new_cursor = max(r["base_arxiv_id"] for r in raw_entries)
            if not cursor_value or new_cursor > cursor_value:
                self.store.set_cursor(cursor_key, new_cursor)

        return new_count, len(raw_entries)

    async def ingest_all_categories(
        self,
        max_results: int = 200,
        force_all: bool = False,
    ) -> dict[str, tuple[int, int]]:
        """Fetch **all** configured arXiv categories.

        Respects ``REQUEST_INTERVAL_S`` between requests.

        Returns a dict mapping ``category → (new_count, total_count)``.
        """
        config = load_sources_config()
        categories: list[str] = []
        for group in config.get("arxiv", {}).get("categories", {}).values():
            if isinstance(group, list):
                categories.extend(group)

        results: dict[str, tuple[int, int]] = {}
        for cat in categories:
            new_c, total_c = await self.ingest_category(cat, max_results, force_all)
            results[cat] = (new_c, total_c)
            await asyncio.sleep(REQUEST_INTERVAL_S)

        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_arxiv_id(url: str) -> str | None:
        """Extract e.g. ``2607.12345v2`` from an arXiv URL."""
        m = ARXIV_ID_RE.search(url)
        return m.group(0) if m else None

    @staticmethod
    def _normalize_abstract(text: str) -> str:
        lines = [l.strip() for l in text.splitlines()]
        return " ".join(l for l in lines if l)

    @staticmethod
    def _text(elem: ElementTree.Element | None) -> str | None:
        if elem is not None and elem.text:
            return elem.text.strip()
        return None

    async def close(self) -> None:
        await self.http.aclose()
