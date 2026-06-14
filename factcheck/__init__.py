"""
FactCheck Agent — Claim Verification Engine
A rigorous, evidence-based claim verification pipeline for marketing and research documents.
"""

from factcheck.models import (
    Claim,
    Evidence,
    ClaimVerdict,
    VerdictSummary,
    FactCheckReport,
)
from factcheck.extractor import extract_text_from_pdf
from factcheck.analyzer import FactCheckAnalyzer

__all__ = [
    "Claim",
    "Evidence",
    "ClaimVerdict",
    "VerdictSummary",
    "FactCheckReport",
    "extract_text_from_pdf",
    "FactCheckAnalyzer",
]
