"""
Data models for the FactCheck Agent pipeline.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ClaimType(str, Enum):
    STATISTICAL = "Statistical"
    FINANCIAL = "Financial"
    TEMPORAL = "Temporal"
    COMPARATIVE = "Comparative"
    SCIENTIFIC = "Scientific"
    REGULATORY = "Regulatory"
    ATTRIBUTION = "Attribution"


class Verdict(str, Enum):
    VERIFIED = "VERIFIED"
    INACCURATE = "INACCURATE"
    FALSE = "FALSE"
    UNVERIFIED = "UNVERIFIED"


class ConfidenceLevel(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


VERDICT_SYMBOLS = {
    Verdict.VERIFIED: "✅",
    Verdict.INACCURATE: "⚠️",
    Verdict.FALSE: "❌",
    Verdict.UNVERIFIED: "🔍",
}

VERDICT_PENALTIES = {
    Verdict.VERIFIED: 0,
    Verdict.INACCURATE: -5,
    Verdict.FALSE: -10,
    Verdict.UNVERIFIED: -2,
}


class Claim(BaseModel):
    claim_id: str = Field(..., description="Unique claim ID (e.g. C001)")
    claim_text: str = Field(..., description="Verbatim text from source doc")
    claim_type: ClaimType
    claim_source_in_doc: Optional[str] = None


class Evidence(BaseModel):
    source_name: str
    source_url: str
    publication_date: Optional[str] = None
    relevant_excerpt: str


class ClaimVerdict(BaseModel):
    claim_id: str
    claim_text: str
    claim_type: ClaimType
    verdict: Verdict
    verdict_symbol: str = ""
    correct_fact: Optional[str] = None
    evidence: list[Evidence] = Field(default_factory=list)
    confidence_score: ConfidenceLevel = ConfidenceLevel.MEDIUM
    analyst_note: Optional[str] = None

    def model_post_init(self, __context) -> None:
        if not self.verdict_symbol:
            self.verdict_symbol = VERDICT_SYMBOLS.get(self.verdict, "")


class VerdictSummary(BaseModel):
    VERIFIED: int = 0
    INACCURATE: int = 0
    FALSE: int = 0
    UNVERIFIED: int = 0


class FactCheckReport(BaseModel):
    document_title: str
    analysis_timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )
    total_claims_extracted: int = 0
    verdict_summary: VerdictSummary = Field(default_factory=VerdictSummary)
    overall_trust_score: int = 100
    claims: list[ClaimVerdict] = Field(default_factory=list)
    executive_summary: str = ""

    def compute_trust_score(self) -> int:
        score = 100
        has_false = False

        for claim in self.claims:
            penalty = VERDICT_PENALTIES.get(claim.verdict, 0)
            score += penalty
            if claim.verdict == Verdict.FALSE:
                has_false = True

        score = max(0, score)

        if has_false and score > 80:
            score = 80

        self.overall_trust_score = score
        return score

    def compute_verdict_summary(self) -> VerdictSummary:
        summary = VerdictSummary()
        for claim in self.claims:
            if claim.verdict == Verdict.VERIFIED:
                summary.VERIFIED += 1
            elif claim.verdict == Verdict.INACCURATE:
                summary.INACCURATE += 1
            elif claim.verdict == Verdict.FALSE:
                summary.FALSE += 1
            elif claim.verdict == Verdict.UNVERIFIED:
                summary.UNVERIFIED += 1

        self.verdict_summary = summary
        self.total_claims_extracted = len(self.claims)
        return summary

