from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from collections import Counter

from .http import HttpClient

# Mapping of common ISO 3166-1 alpha-2 country codes to Spanish names
_COUNTRY_NAMES: dict[str, str] = {
    "US": "Estados Unidos", "GB": "Reino Unido", "DE": "Alemania", "FR": "Francia",
    "ES": "España", "IT": "Italia", "CN": "China", "JP": "Japón", "CA": "Canadá",
    "AU": "Australia", "BR": "Brasil", "IN": "India", "KR": "Corea del Sur",
    "NL": "Países Bajos", "SE": "Suecia", "CH": "Suiza", "MX": "México",
    "PT": "Portugal", "AR": "Argentina", "CL": "Chile", "CO": "Colombia",
    "BE": "Bélgica", "AT": "Austria", "DK": "Dinamarca", "NO": "Noruega",
    "FI": "Finlandia", "PL": "Polonia", "IL": "Israel", "IE": "Irlanda",
    "SA": "Arabia Saudí", "TR": "Turquía", "RU": "Rusia", "ZA": "Sudáfrica",
    "RS": "Serbia", "EG": "Egipto", "IR": "Irán", "TW": "Taiwán",
    "SG": "Singapur", "NZ": "Nueva Zelanda", "CZ": "Chequia", "GR": "Grecia",
    "HU": "Hungría", "RO": "Rumanía", "TH": "Tailandia", "MY": "Malasia",
    "PK": "Pakistán", "NG": "Nigeria", "CU": "Cuba", "PE": "Perú",
}


@dataclass
class OpenAlexWork:
    doi: str
    openalex_id: str
    cited_by_count: int
    field_normalized_citation_impact: Optional[float]
    citation_percentile: Optional[float]
    primary_location: Optional[str]
    concepts: list[str]
    publication_year: Optional[int]
    journal: Optional[str]
    abstract: Optional[str] = None
    citing_context: Optional[dict[str, Any]] = None


class OpenAlexClient:
    BASE = "https://api.openalex.org"

    def __init__(self, http: HttpClient | None = None, mailto: str | None = None):
        self.http = http or HttpClient()
        self.mailto = mailto

    def fetch_by_doi(self, doi: str, include_citing_context: bool = False) -> OpenAlexWork:
        # OpenAlex expects DOI with https://doi.org/ prefix when filtering
        doi_norm = doi.strip()
        url = f"{self.BASE}/works"
        params = {"filter": f"doi:https://doi.org/{doi_norm}", "per-page": 1}
        if self.mailto:
            params["mailto"] = self.mailto

        r = self.http.get(url, params=params)
        r.raise_for_status()
        data = r.json()
        results = data.get("results") or []
        if not results:
            raise ValueError(f"OpenAlex: DOI not found: {doi_norm}")

        w = results[0]
        cited_by_count = int(w.get("cited_by_count") or 0)

        # Field-weighted citation impact (open proxy for FWCI/CNCI)
        fnci = w.get("fwci")
        try:
            fnci = float(fnci) if fnci is not None else None
        except Exception:
            fnci = None

        # Citation percentile (0-100 scale).
        # Primary: citation_normalized_percentile.value (0-1 scale, convert to 0-100).
        # Fallback: cited_by_percentile_year.max.
        percentile = None
        cnp = w.get("citation_normalized_percentile")
        if isinstance(cnp, dict) and cnp.get("value") is not None:
            try:
                percentile = float(cnp["value"]) * 100
            except Exception:
                percentile = None
        if percentile is None:
            cpy = w.get("cited_by_percentile_year")
            if isinstance(cpy, dict) and cpy.get("max") is not None:
                try:
                    percentile = float(cpy["max"])
                except Exception:
                    percentile = None

        # OpenAlex migrated from concepts to topics; try topics first
        concepts = []
        for t in (w.get("topics") or [])[:5]:
            name = t.get("display_name")
            if name:
                concepts.append(name)
        if not concepts:
            for c in (w.get("concepts") or [])[:5]:
                name = c.get("display_name")
                if name:
                    concepts.append(name)

        pub_year = w.get("publication_year")
        try:
            pub_year = int(pub_year) if pub_year is not None else None
        except Exception:
            pub_year = None

        journal = None
        primary_location = None
        host = (w.get("primary_location") or {}).get("source")
        if isinstance(host, dict):
            journal = host.get("display_name")
        pl = w.get("primary_location")
        if isinstance(pl, dict):
            primary_location = pl.get("landing_page_url")

        # Reconstruct abstract from inverted index
        abstract = None
        inv = w.get("abstract_inverted_index")
        if isinstance(inv, dict) and inv:
            words: dict[int, str] = {}
            for word, positions in inv.items():
                for pos in positions:
                    words[pos] = word
            if words:
                abstract = " ".join(words[i] for i in sorted(words.keys()))

        citing_context = None
        if include_citing_context:
            openalex_id = w.get("id")
            citing_context = self._fetch_citing_context(openalex_id)

        return OpenAlexWork(
            doi=doi_norm,
            openalex_id=w.get("id"),
            cited_by_count=cited_by_count,
            field_normalized_citation_impact=fnci,
            citation_percentile=percentile,
            primary_location=primary_location,
            concepts=concepts,
            publication_year=pub_year,
            journal=journal,
            abstract=abstract,
            citing_context=citing_context,
        )

    def _fetch_citing_context(self, openalex_id: str | None) -> Optional[dict[str, Any]]:
        if not openalex_id:
            return None
        url = f"{self.BASE}/works"
        params = {
            "filter": f"cites:{openalex_id}",
            "per-page": 25,
            "select": "authorships,topics,concepts,publication_year",
        }
        if self.mailto:
            params["mailto"] = self.mailto

        r = self.http.get(url, params=params)
        if r.status_code >= 400:
            return {"notes": "Unable to fetch citing works", "status_code": r.status_code}
        data = r.json()
        results = data.get("results") or []

        country_counts: Counter[str] = Counter()
        inst_counts: Counter[str] = Counter()
        concept_counts: Counter[str] = Counter()

        for cw in results:
            topics = (cw.get("topics") or [])[:3]
            if not topics:
                topics = (cw.get("concepts") or [])[:3]
            for c in topics:
                name = c.get("display_name")
                if name:
                    concept_counts[name] += 1

            for a in (cw.get("authorships") or []):
                for inst in (a.get("institutions") or [])[:2]:
                    name = inst.get("display_name")
                    if name:
                        inst_counts[name] += 1
                    cc = inst.get("country_code")
                    if cc:
                        country_counts[cc] += 1

        top_countries = [_COUNTRY_NAMES.get(c, c) for c, _ in country_counts.most_common(5)]
        top_institutions = [i for i, _ in inst_counts.most_common(5)]
        top_concepts = [c for c, _ in concept_counts.most_common(5)]

        return {
            "sample_size": len(results),
            "top_countries": top_countries,
            "top_institutions": top_institutions,
            "top_concepts": top_concepts,
            "notes": "Citing-context computed from first 25 citing works (sample).",
        }
