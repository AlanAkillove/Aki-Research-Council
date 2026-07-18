"""Paper identity normalization and version merge (stubs)."""

from __future__ import annotations

import re
import unicodedata


def title_fingerprint(title: str) -> str:
    text = unicodedata.normalize("NFKC", title).lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def pick_canonical_id(
    *,
    doi: str | None = None,
    arxiv_id: str | None = None,
    openreview_id: str | None = None,
    semantic_scholar_id: str | None = None,
    title: str | None = None,
) -> str:
    """DOI > arXiv > OpenReview > S2 > title fingerprint."""
    if doi:
        return f"doi:{doi.strip().lower()}"
    if arxiv_id:
        return f"arxiv:{arxiv_id.strip()}"
    if openreview_id:
        return f"openreview:{openreview_id.strip()}"
    if semantic_scholar_id:
        return f"s2:{semantic_scholar_id.strip()}"
    if title:
        return f"title:{title_fingerprint(title)}"
    raise ValueError("No identity fields available for canonical_id")
