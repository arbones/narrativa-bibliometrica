from __future__ import annotations

from typing import Any


def validate_report(report: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    ident = report.get("identity") or {}
    metrics = report.get("metrics") or {}

    def add(level: str, message: str):
        checks.append({"level": level, "message": message})

    if not ident.get("doi") and not ident.get("pmid"):
        add("fail", "Missing both DOI and PMID")

    if "citations_total" not in metrics:
        add("fail", "Missing citations_total")

    nci = (metrics.get("normalized_citation_impact") or {}).get("value")
    if nci is None:
        add("warning", "Missing normalized_citation_impact (OpenAlex proxy)")

    p = (metrics.get("citation_percentile") or {}).get("value")
    if p is None:
        add("warning", "Missing citation_percentile")

    if not ident.get("journal"):
        add("warning", "Missing journal name")

    if not ident.get("year"):
        add("warning", "Missing publication year")

    return {"checks": checks, "ok": not any(c["level"] == "fail" for c in checks)}


def validate_batch(reports: list[dict[str, Any]]) -> dict[str, Any]:
    out = []
    ok = True
    for r in reports:
        vr = validate_report(r)
        ok = ok and bool(vr.get("ok"))
        out.append(vr)
    return {"ok": ok, "results": out}
