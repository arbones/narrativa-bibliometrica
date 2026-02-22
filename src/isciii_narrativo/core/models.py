from __future__ import annotations

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


Confidence = Literal["high", "medium", "low"]


class WorkIdentity(BaseModel):
    input_id: str = Field(..., description="Original identifier provided by the user")
    id_type: Literal["doi", "pmid", "unknown"]

    doi: Optional[str] = None
    pmid: Optional[str] = None

    title: Optional[str] = None
    year: Optional[int] = None
    journal: Optional[str] = None
    issn: Optional[str] = None
    eissn: Optional[str] = None


class MetricSnapshot(BaseModel):
    metric_name: str
    value: Any
    unit: Optional[str] = None

    source: Literal["OpenAlex", "PubMed", "Crossref", "Derived"]
    retrieved_at: str
    query: Optional[str] = None

    confidence: Confidence = "high"
    notes: Optional[str] = None


class WorkReport(BaseModel):
    identity: WorkIdentity
    metrics: dict[str, MetricSnapshot] = Field(default_factory=dict)
    paragraph: Optional[str] = None
    relevance_prompt: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)
