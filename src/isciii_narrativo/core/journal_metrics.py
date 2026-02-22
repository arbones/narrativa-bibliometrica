from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class JCRInfo:
    """Journal-level metrics from JCR (Clarivate / Web of Science).

    Source: abdullahfarhan.com – JCR 2025 release (based on 2024 citation data).
    """
    journal_name: str
    jif: Optional[float]
    jif_5yr: Optional[float]
    jif_quartile: Optional[int]  # Best quartile (1-4)
    category: Optional[str]  # raw, e.g. "ONCOLOGY|Q1|1/322"
    category_name: Optional[str]
    category_quartile: Optional[int]
    category_rank: Optional[str]  # e.g. "1/322"
    issn: Optional[str]
    eissn: Optional[str]


def _parse_quartile(value: str) -> Optional[int]:
    """Parse 'Q1' → 1, 'Q2' → 2, etc."""
    m = re.match(r"Q([1-4])", value.strip())
    return int(m.group(1)) if m else None


def _parse_jcr_category(raw: str | None) -> tuple[str | None, int | None, str | None]:
    """Parse JCR category string like 'ONCOLOGY|Q1|1/322'."""
    if not raw:
        return None, None, None
    parts = raw.split("|")
    cat_name = parts[0].strip() if len(parts) > 0 else None
    quartile = None
    if len(parts) > 1:
        m = re.match(r"Q([1-4])", parts[1].strip())
        quartile = int(m.group(1)) if m else None
    rank_str = parts[2].strip() if len(parts) > 2 else None
    return cat_name, quartile, rank_str


def _float_or_none(v: str | None) -> float | None:
    if not v or v.strip() in ("", "N/A", "-"):
        return None
    try:
        return float(v.strip())
    except ValueError:
        return None


def _normalize_issn(issn: str) -> str | None:
    """Normalize ISSN to 'XXXX-XXXX' format, return None for 'N/A'."""
    v = issn.strip()
    if not v or v.upper() == "N/A":
        return None
    v = v.replace("-", "")
    if len(v) == 8:
        return f"{v[:4]}-{v[4:]}"
    return v


class JCRLookup:
    """In-memory lookup of JCR journal impact factors from bundled CSV.

    Data source: abdullahfarhan.com – JCR 2025 release (2024 citation data).
    """

    def __init__(self, csv_path: Path | None = None):
        if csv_path is None:
            csv_path = Path(__file__).resolve().parent.parent / "data" / "jcr_2024.csv"
        self._csv_path = csv_path
        self._by_issn: dict[str, JCRInfo] = {}
        self._by_title: dict[str, JCRInfo] = {}
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not self._csv_path.exists():
            return
        with open(self._csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cat_name, cat_q, cat_rank = _parse_jcr_category(row.get("category"))
                jif_q = _parse_quartile(row.get("jif_quartile", ""))
                info = JCRInfo(
                    journal_name=row["journal_name"].strip(),
                    jif=_float_or_none(row.get("jif")),
                    jif_5yr=_float_or_none(row.get("jif_5yr")),
                    jif_quartile=jif_q,
                    category=row.get("category"),
                    category_name=cat_name,
                    category_quartile=cat_q,
                    category_rank=cat_rank,
                    issn=_normalize_issn(row.get("issn", "")),
                    eissn=_normalize_issn(row.get("eissn", "")),
                )
                for val in (info.issn, info.eissn):
                    if val:
                        self._by_issn[val] = info
                        self._by_issn[val.replace("-", "")] = info
                self._by_title[info.journal_name.lower()] = info

    def find(self, issn: str | None = None, eissn: str | None = None, title: str | None = None) -> JCRInfo | None:
        """Try ISSN, eISSN, then title to find JCR info."""
        self._load()
        for candidate in (issn, eissn):
            if candidate:
                clean = candidate.strip().replace("-", "")
                if clean in self._by_issn:
                    return self._by_issn[clean]
                dashed = f"{clean[:4]}-{clean[4:]}" if len(clean) == 8 else clean
                if dashed in self._by_issn:
                    return self._by_issn[dashed]
        if title:
            return self._by_title.get(title.strip().lower())
        return None
