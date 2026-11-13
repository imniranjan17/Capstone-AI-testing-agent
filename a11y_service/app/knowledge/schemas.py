from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, field_validator

Authority = Literal[
    "normative", "official_explanatory", "official_technique", "tool_mapping",
    "internal_guidance", "historical_fix",
]

# Lower number = higher authority (used to prefer normative evidence on near-ties).
AUTHORITY_RANK: dict[str, int] = {
    "normative": 0, "official_explanatory": 1, "official_technique": 2,
    "tool_mapping": 3, "internal_guidance": 4, "historical_fix": 5,
}


class Chunk(BaseModel):
    chunk_id: str
    document_id: str
    document: str
    document_version: str
    authority: Authority
    principle: str = ""
    guideline: str = ""
    success_criterion: str  # for explanatory chunks: the parent criterion
    title: str = ""
    level: str = ""  # A | AA | AAA
    section_type: str = "criterion"
    content: str
    source_url: str
    retrieved: str
    checksum: str

    @field_validator("source_url", "document", "content", "checksum")
    @classmethod
    def _provenance_required(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("chunk is missing required provenance/content")
        return v

    def index_text(self) -> str:
        """Text used for embedding / lexical indexing / reranking: ID and title always retained."""
        return f"SC {self.success_criterion} {self.title} (Level {self.level}) [{self.section_type}]: {self.content}"


class RetrievalFilter(BaseModel):
    document_version: str = "2.2"
    levels: list[str] = ["A", "AA"]
    authorities: Optional[list[str]] = None
    success_criteria: Optional[list[str]] = None

    def matches(self, c: Chunk) -> bool:
        if c.document_version != self.document_version and c.authority in ("normative", "official_explanatory"):
            return False
        if c.level and c.level not in self.levels:
            return False
        if self.authorities and c.authority not in self.authorities:
            return False
        if self.success_criteria and c.success_criterion not in self.success_criteria:
            return False
        return True
