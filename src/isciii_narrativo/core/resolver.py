from __future__ import annotations

import re
from typing import Optional

from .models import WorkIdentity
from .pubmed_client import PubMedClient
from .crossref_client import CrossrefClient


_DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)


def detect_id_type(value: str) -> str:
    v = value.strip()
    if v.isdigit():
        return "pmid"
    # strip doi: prefix / URL
    v2 = v
    v2 = re.sub(r"^(doi:)\s*", "", v2, flags=re.IGNORECASE)
    v2 = re.sub(r"^https?://(dx\.)?doi\.org/", "", v2, flags=re.IGNORECASE)
    if _DOI_RE.match(v2):
        return "doi"
    return "unknown"


def normalize_doi(value: str) -> Optional[str]:
    v = value.strip()
    v = re.sub(r"^(doi:)\s*", "", v, flags=re.IGNORECASE)
    v = re.sub(r"^https?://(dx\.)?doi\.org/", "", v, flags=re.IGNORECASE)
    v = v.strip()
    if _DOI_RE.match(v):
        return v
    return None


class Resolver:
    def __init__(self, pubmed: PubMedClient | None = None, crossref: CrossrefClient | None = None):
        self.pubmed = pubmed or PubMedClient()
        self.crossref = crossref or CrossrefClient()

    def resolve_one(self, input_id: str) -> WorkIdentity:
        id_type = detect_id_type(input_id)
        ident = WorkIdentity(input_id=input_id, id_type=id_type)

        if id_type == "pmid":
            rec = self.pubmed.fetch_basic(input_id.strip())
            ident.pmid = rec.pmid
            ident.doi = rec.doi
            ident.title = rec.title
            ident.year = rec.year
            ident.journal = rec.journal
            if rec.doi:
                # enrich via Crossref to get ISSN
                try:
                    cr = self.crossref.fetch_work(rec.doi)
                    ident.issn = cr.issn
                    ident.eissn = cr.eissn
                    ident.journal = ident.journal or cr.journal
                    ident.title = ident.title or cr.title
                    ident.year = ident.year or cr.year
                except Exception:
                    pass
            return ident

        if id_type == "doi":
            doi = normalize_doi(input_id) or input_id.strip()
            ident.doi = doi
            try:
                cr = self.crossref.fetch_work(doi)
                ident.title = cr.title
                ident.year = cr.year
                ident.journal = cr.journal
                ident.issn = cr.issn
                ident.eissn = cr.eissn
            except Exception:
                pass
            # Try to find PMID via PubMed search by DOI (optional)
            # Keep it lightweight: skip to avoid extra calls and rate limits.
            return ident

        # unknown
        # try as DOI anyway
        doi = normalize_doi(input_id)
        if doi:
            ident.id_type = "doi"
            ident.doi = doi
            try:
                cr = self.crossref.fetch_work(doi)
                ident.title = cr.title
                ident.year = cr.year
                ident.journal = cr.journal
                ident.issn = cr.issn
                ident.eissn = cr.eissn
            except Exception:
                pass
        return ident

    def resolve_batch(self, ids: list[str]) -> list[WorkIdentity]:
        return [self.resolve_one(x) for x in ids]
