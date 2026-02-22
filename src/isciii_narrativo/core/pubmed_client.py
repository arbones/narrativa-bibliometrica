from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import xml.etree.ElementTree as ET

from .http import HttpClient


@dataclass
class PubMedRecord:
    pmid: str
    title: Optional[str] = None
    year: Optional[int] = None
    journal: Optional[str] = None
    doi: Optional[str] = None
    abstract: Optional[str] = None


class PubMedClient:
    """Minimal PubMed (NCBI E-utilities) client.

    Uses only open endpoints.
    """

    BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(self, http: HttpClient | None = None, tool: str = "isciii-narrativo"):
        self.http = http or HttpClient()
        self.tool = tool

    def fetch_basic(self, pmid: str) -> PubMedRecord:
        # esummary JSON for basic metadata
        url = f"{self.BASE}/esummary.fcgi"
        r = self.http.get(
            url,
            params={
                "db": "pubmed",
                "id": pmid,
                "retmode": "json",
                "tool": self.tool,
            },
        )
        r.raise_for_status()
        data = r.json()
        result = data.get("result", {})
        item = result.get(pmid, {})

        title = item.get("title")
        journal = item.get("fulljournalname")
        pubdate = (item.get("pubdate") or "").strip()
        year = None
        if pubdate:
            # pubdate is often "2021 Jan" or "2021"
            try:
                year = int(pubdate.split()[0])
            except Exception:
                year = None

        doi, abstract = self._fetch_efetch_fields(pmid)
        return PubMedRecord(pmid=pmid, title=title, journal=journal, year=year, doi=doi, abstract=abstract)

    def _fetch_efetch_fields(self, pmid: str) -> tuple[Optional[str], Optional[str]]:
        """Fetch DOI and abstract from efetch XML for a given PMID."""
        url = f"{self.BASE}/efetch.fcgi"
        r = self.http.get(
            url,
            params={
                "db": "pubmed",
                "id": pmid,
                "retmode": "xml",
                "tool": self.tool,
            },
            headers={"Accept": "application/xml"},
        )
        r.raise_for_status()
        try:
            root = ET.fromstring(r.text)
        except Exception:
            return None, None

        doi = None
        for article_id in root.findall(".//ArticleId"):
            if article_id.attrib.get("IdType") == "doi":
                doi = (article_id.text or "").strip() or None
                break

        abstract = None
        abs_els = root.findall(".//AbstractText")
        if abs_els:
            parts = []
            for el in abs_els:
                text = "".join(el.itertext()).strip()
                if text:
                    parts.append(text)
            abstract = " ".join(parts).strip() or None

        return doi, abstract

    def fetch_abstract_by_doi(self, doi: str) -> Optional[str]:
        """Search PubMed by DOI and return the abstract if found."""
        # Step 1: esearch DOI → PMID
        url = f"{self.BASE}/esearch.fcgi"
        r = self.http.get(
            url,
            params={
                "db": "pubmed",
                "term": f"{doi}[doi]",
                "retmode": "json",
                "tool": self.tool,
            },
        )
        r.raise_for_status()
        data = r.json()
        id_list = data.get("esearchresult", {}).get("idlist", [])
        if not id_list:
            return None

        # Step 2: efetch for abstract
        pmid = id_list[0]
        _, abstract = self._fetch_efetch_fields(pmid)
        return abstract
