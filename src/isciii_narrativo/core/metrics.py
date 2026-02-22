from __future__ import annotations

from .models import MetricSnapshot
from .openalex_client import OpenAlexWork


def build_openalex_metrics(work: OpenAlexWork, retrieved_at: str, query: str, include_citing_context: bool) -> dict[str, MetricSnapshot]:
    m: dict[str, MetricSnapshot] = {}

    m["citations_total"] = MetricSnapshot(
        metric_name="citations_total",
        value=work.cited_by_count,
        unit="count",
        source="OpenAlex",
        retrieved_at=retrieved_at,
        query=query,
        confidence="high",
    )

    m["normalized_citation_impact"] = MetricSnapshot(
        metric_name="normalized_citation_impact",
        value=work.field_normalized_citation_impact,
        unit="ratio",
        source="OpenAlex",
        retrieved_at=retrieved_at,
        query=query,
        confidence="medium" if work.field_normalized_citation_impact is None else "high",
        notes="OpenAlex field_normalized_citation_impact (open proxy for FWCI/CNCI).",
    )

    m["citation_percentile"] = MetricSnapshot(
        metric_name="citation_percentile",
        value=work.citation_percentile,
        unit="percentile_0_100",
        source="OpenAlex",
        retrieved_at=retrieved_at,
        query=query,
        confidence="low" if work.citation_percentile is None else "high",
        notes="OpenAlex cited_by_percentile_year (if available).",
    )

    if include_citing_context:
        m["citing_context"] = MetricSnapshot(
            metric_name="citing_context",
            value=work.citing_context,
            unit=None,
            source="OpenAlex",
            retrieved_at=retrieved_at,
            query=(work.primary_location or query),
            confidence="medium" if work.citing_context else "low",
            notes="Derived from a limited sample of citing works for efficiency.",
        )

    return m
