from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .http import HttpClient


@dataclass
class CrossrefRecord:
    doi: str
    title: Optional[str] = None
    year: Optional[int] = None
    journal: Optional[str] = None
    issn: Optional[str] = None
    eissn: Optional[str] = None


class CrossrefClient:
    BASE = "https://api.crossref.org/works"

    def __init__(self, http: HttpClient | None = None):
        self.http = http or HttpClient()

    def fetch_work(self, doi: str) -> CrossrefRecord:
        url = f"{self.BASE}/{doi}"
        r = self.http.get(url)
        r.raise_for_status()
        msg = r.json().get("message", {})

        title_list = msg.get("title") or []
        title = title_list[0] if title_list else None

        year = None
        issued = msg.get("issued", {}).get("date-parts")
        if issued and isinstance(issued, list) and issued[0] and isinstance(issued[0], list):
            try:
                year = int(issued[0][0])
            except Exception:
                year = None

        journal = None
        container = msg.get("container-title") or []
        if container:
            journal = container[0]

        # Crossref can return multiple ISSNs with type info
        issn = None
        eissn = None
        issn_list = msg.get("issn-type") or []
        for it in issn_list:
            t = (it.get("type") or "").lower()
            v = it.get("value")
            if not v:
                continue
            if t in ("print", "ppub") and not issn:
                issn = v
            if t in ("electronic", "epub") and not eissn:
                eissn = v
        if not issn:
            raw = msg.get("ISSN")
            if isinstance(raw, list) and raw:
                issn = raw[0]

        return CrossrefRecord(doi=doi, title=title, year=year, journal=journal, issn=issn, eissn=eissn)
