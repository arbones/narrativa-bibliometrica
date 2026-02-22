from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape


@dataclass
class NarrativeInput:
    title: Optional[str]
    year: Optional[int]
    journal: Optional[str]
    citations: int
    nci: Optional[float]
    article_percentile: Optional[float]
    top_label: Optional[str]
    concepts: list[str]
    citing_context_text: Optional[str]
    abstract: Optional[str]
    date: str
    # Journal-level metrics from JCR (Clarivate / Web of Science)
    jif: Optional[float] = None
    jif_quartile: Optional[int] = None
    jif_category: Optional[str] = None


def nci_explanation(nci: Optional[float]) -> Optional[str]:
    """Return a human-readable Spanish explanation of the NCI (FWCI) value."""
    if nci is None:
        return None
    if nci >= 10:
        return f"lo que indica que ha recibido más de diez veces las citas que el promedio mundial para artículos similares en su campo y año de publicación"
    if nci >= 5:
        return f"lo que indica que ha recibido más de cinco veces las citas que el promedio mundial para artículos similares en su campo y año de publicación"
    if nci >= 2:
        return f"lo que indica que ha recibido más del doble de citas que el promedio mundial para artículos similares en su campo y año de publicación"
    if nci >= 1.5:
        return f"lo que indica que ha recibido un 50% más de citas que el promedio mundial para artículos similares en su campo y año de publicación"
    if nci >= 1.0:
        return f"lo que indica que se encuentra en torno al promedio mundial de citas para artículos similares en su campo y año de publicación"
    return f"lo que indica que se encuentra por debajo del promedio mundial de citas para artículos similares en su campo y año de publicación"


class NarrativeGenerator:
    def __init__(self, templates_dir: Path):
        self.env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(disabled_extensions=("jinja2",)),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.env.filters["nci_explanation"] = lambda v: nci_explanation(v) or ""

    @staticmethod
    def today_str() -> str:
        return datetime.now().strftime("%d/%m/%Y")

    def render(self, template: str, ctx: NarrativeInput, max_chars: int | None = None) -> tuple[str, list[str]]:
        warnings: list[str] = []
        tpl_name = "short_es.jinja2" if template == "short" else "extended_es.jinja2"
        t = self.env.get_template(tpl_name)
        text = t.render(**ctx.__dict__).strip()

        if max_chars is not None and len(text) > max_chars:
            text = text[: max(0, max_chars - 1)].rstrip() + "…"
            warnings.append(f"Paragraph truncated to {max_chars} characters")

        return text, warnings

    def render_relevance_prompt(self, ctx: NarrativeInput) -> str | None:
        """Render a prompt for the calling LLM to generate the relevance paragraph."""
        if not ctx.abstract:
            return None
        t = self.env.get_template("relevance_es.jinja2")
        return t.render(**ctx.__dict__).strip()


def top_label_from_percentile(p: Optional[float]) -> Optional[str]:
    if p is None:
        return None
    try:
        p = float(p)
    except Exception:
        return None
    if p >= 99:
        return "top 1% por citación"
    if p >= 95:
        return "top 5% por citación"
    if p >= 90:
        return "top 10% por citación"
    if p >= 75:
        return "top 25% por citación"
    # For percentiles below 75, no special label
    return None


def citing_context_to_text(ctx: Optional[dict]) -> Optional[str]:
    if not ctx:
        return None
    if "notes" in ctx and ctx.get("sample_size") in (None, 0):
        return None

    parts: list[str] = []
    ss = ctx.get("sample_size")
    if ss:
        parts.append(f"Contexto de citación basado en una muestra de {ss} documentos citantes.")

    countries = ctx.get("top_countries") or []
    if countries:
        parts.append("Países citantes predominantes: " + ", ".join(countries) + ".")

    inst = ctx.get("top_institutions") or []
    if inst:
        parts.append("Instituciones citantes frecuentes: " + ", ".join(inst[:3]) + ("." if len(inst) <= 3 else ", etc."))

    concepts = ctx.get("top_concepts") or []
    if concepts:
        parts.append("Temas dominantes en citantes: " + ", ".join(concepts) + ".")

    return " ".join(parts).strip() if parts else None
