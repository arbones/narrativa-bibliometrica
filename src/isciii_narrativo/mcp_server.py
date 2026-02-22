from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from .core.http import HttpClient
from .core.pubmed_client import PubMedClient
from .core.crossref_client import CrossrefClient
from .core.openalex_client import OpenAlexClient
from .core.resolver import Resolver
from .core.metrics import build_openalex_metrics
from .core.models import WorkReport
from .core.narrative import (
    NarrativeGenerator,
    NarrativeInput,
    top_label_from_percentile,
    citing_context_to_text,
)
from .core.journal_metrics import JCRLookup
from .core.validator import validate_batch


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


mcp = FastMCP("isciii-narrativo")


def _pubmed_abstract(pubmed: PubMedClient, doi: str) -> str | None:
    """Fallback: fetch abstract from PubMed when OpenAlex doesn't have it."""
    time.sleep(0.4)  # respect NCBI rate limit (~3 req/s without API key)
    try:
        return pubmed.fetch_abstract_by_doi(doi)
    except Exception:
        return None


@mcp.tool()
def resolve_ids(ids: list[str]) -> dict[str, Any]:
    """Resolve a batch of DOIs/PMIDs into normalized identities (open sources only)."""
    http = HttpClient()
    try:
        resolver = Resolver(pubmed=PubMedClient(http=http), crossref=CrossrefClient(http=http))
        identities = [x.model_dump() for x in resolver.resolve_batch(ids)]
        return {"retrieved_at": _now_iso(), "identities": identities}
    finally:
        http.close()


@mcp.tool()
def fetch_open_metrics_batch(dois: list[str], include_citing_context: bool = False, mailto: str | None = None) -> dict[str, Any]:
    """Fetch open bibliometric metrics for a batch of DOIs using OpenAlex."""
    http = HttpClient()
    try:
        oa = OpenAlexClient(http=http, mailto=mailto)
        retrieved_at = _now_iso()
        out = []
        for doi in dois:
            doi_clean = doi.strip()
            query = f"https://api.openalex.org/works?filter=doi:https%3A%2F%2Fdoi.org%2F{doi_clean}"
            try:
                w = oa.fetch_by_doi(doi_clean, include_citing_context=include_citing_context)
                metrics = build_openalex_metrics(w, retrieved_at=retrieved_at, query=query, include_citing_context=include_citing_context)
                out.append({"doi": doi_clean, "metrics": {k: v.model_dump() for k, v in metrics.items()}})
            except Exception as e:
                out.append({"doi": doi_clean, "error": str(e)})

        return {"retrieved_at": retrieved_at, "results": out}
    finally:
        http.close()


@mcp.tool()
def generar_narrativa(
    ids: list[str],
    template: Literal["short", "extended"] = "short",
    max_chars: int = 1500,
    include_citing_context: bool = False,
    mailto: str | None = None,
) -> dict[str, Any]:
    """End-to-end: resolve identifiers, fetch metrics, generate ISCIII-style Spanish narrative.

    Returns for each work:
    - `paragraph`: first paragraph with quantitative bibliometric indicators (ready to use).
    - `relevance_prompt`: when present, you MUST follow its instructions to generate a
      second paragraph and append it to `paragraph` before presenting the result to the user.
      The second paragraph highlights the work's transferability, clinical application,
      methodological contribution, public health impact, and policy relevance.
      Write it in Spanish, 3-5 natural sentences, no headers or bullet points.

    IMPORTANT: Always present BOTH paragraphs together as a single block of text per work.
    If `relevance_prompt` is null (no abstract available), present only the first paragraph.
    """

    http = HttpClient()
    try:
        pubmed = PubMedClient(http=http)
        resolver = Resolver(pubmed=pubmed, crossref=CrossrefClient(http=http))
        oa = OpenAlexClient(http=http, mailto=mailto)
        jcr = JCRLookup()
        templates_dir = Path(__file__).resolve().parent / "templates"
        ng = NarrativeGenerator(templates_dir=templates_dir)

        retrieved_at = _now_iso()
        date_str = ng.today_str()

        def _jcr_fields(jcr_info) -> dict:
            """Extract JCR fields for NarrativeInput from a JCRInfo or None."""
            if not jcr_info:
                return {}
            cat_str = None
            if jcr_info.category_name:
                cat_str = jcr_info.category_name
                if jcr_info.category_quartile:
                    cat_str += f" (Q{jcr_info.category_quartile}"
                    if jcr_info.category_rank:
                        cat_str += f", {jcr_info.category_rank}"
                    cat_str += ")"
            return dict(
                jif=jcr_info.jif,
                jif_quartile=jcr_info.jif_quartile,
                jif_category=cat_str,
            )

        def _empty_ctx(**overrides) -> NarrativeInput:
            defaults = dict(
                title=None, year=None, journal=None, citations=0,
                nci=None, article_percentile=None, top_label=None,
                concepts=[], citing_context_text=None, abstract=None,
                date=date_str,
            )
            defaults.update(overrides)
            return NarrativeInput(**defaults)

        reports: list[WorkReport] = []
        for input_id in ids:
            ident = resolver.resolve_one(input_id)
            wr = WorkReport(identity=ident)

            # Journal-level metrics from JCR
            jcr_info = jcr.find(issn=ident.issn, eissn=ident.eissn, title=ident.journal)
            jcr_fields = _jcr_fields(jcr_info)

            if not ident.doi:
                wr.warnings.append("Missing DOI; cannot query OpenAlex metrics reliably")
                ctx = _empty_ctx(title=ident.title, year=ident.year, journal=ident.journal, **jcr_fields)
                para, w = ng.render(template=template, ctx=ctx, max_chars=max_chars)
                wr.paragraph = para
                wr.relevance_prompt = ng.render_relevance_prompt(ctx)
                wr.warnings.extend(w)
                reports.append(wr)
                continue

            # OpenAlex metrics
            doi = ident.doi
            query = f"https://api.openalex.org/works?filter=doi:https%3A%2F%2Fdoi.org%2F{doi}"
            try:
                ow = oa.fetch_by_doi(doi, include_citing_context=include_citing_context)
                metrics = build_openalex_metrics(ow, retrieved_at=retrieved_at, query=query, include_citing_context=include_citing_context)
                wr.metrics = {k: v for k, v in metrics.items()}

                citations = int(metrics["citations_total"].value or 0)
                nci = metrics["normalized_citation_impact"].value
                pctl = metrics["citation_percentile"].value
                top_label = top_label_from_percentile(pctl)

                citing_context_text = None
                if include_citing_context:
                    cctx = metrics.get("citing_context")
                    citing_context_text = citing_context_to_text(cctx.value if cctx else None)

                ctx = NarrativeInput(
                    title=ident.title or ow.primary_location,
                    year=ident.year or ow.publication_year,
                    journal=ident.journal or ow.journal,
                    citations=citations,
                    nci=float(nci) if nci is not None else None,
                    article_percentile=float(pctl) if pctl is not None else None,
                    top_label=top_label,
                    concepts=ow.concepts or [],
                    citing_context_text=citing_context_text,
                    abstract=ow.abstract or _pubmed_abstract(pubmed, doi),
                    date=date_str,
                    **jcr_fields,
                )

                para, w = ng.render(template=template, ctx=ctx, max_chars=max_chars)
                wr.paragraph = para
                wr.relevance_prompt = ng.render_relevance_prompt(ctx)
                wr.warnings.extend(w)

                if metrics["citation_percentile"].value is None:
                    wr.warnings.append("OpenAlex citation percentile not available for this work")
                if metrics["normalized_citation_impact"].value is None:
                    wr.warnings.append("OpenAlex normalized impact not available for this work")

            except Exception as e:
                wr.warnings.append(f"Metrics fetch failed: {e}")
                ctx = _empty_ctx(title=ident.title, year=ident.year, journal=ident.journal, **jcr_fields)
                para, w = ng.render(template=template, ctx=ctx, max_chars=max_chars)
                wr.paragraph = para
                wr.relevance_prompt = ng.render_relevance_prompt(ctx)
                wr.warnings.extend(w)

            reports.append(wr)

        # serialize
        out_reports = []
        for r in reports:
            d = r.model_dump()
            if d.get("metrics"):
                d["metrics"] = {k: v for k, v in d["metrics"].items()}
            out_reports.append(d)

        return {"mode": "open", "retrieved_at": retrieved_at, "reports": out_reports}
    finally:
        http.close()


@mcp.tool()
def validate_batch_reports(reports: dict[str, Any]) -> dict[str, Any]:
    """Validate generated reports (checks for missing key fields)."""
    reps = reports.get("reports") if isinstance(reports, dict) else None
    if not isinstance(reps, list):
        return {"ok": False, "error": "Expected an object with a 'reports' list"}
    return validate_batch(reps)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
