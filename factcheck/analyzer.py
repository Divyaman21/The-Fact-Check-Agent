"""
FactCheck Analyzer — LLM-based claim extraction and verification engine.
Uses Google Gemini with web search grounding for evidence-based verification.
"""

from __future__ import annotations

import json
import re
import time
from typing import Callable, Optional

import google.generativeai as genai

from factcheck.models import (
    Claim,
    ClaimType,
    ClaimVerdict,
    ConfidenceLevel,
    Evidence,
    FactCheckReport,
    Verdict,
    VerdictSummary,
    VERDICT_SYMBOLS,
)


def _clean_json_response(text: str) -> str:
    """Strip markdown code fences and extraneous text from LLM JSON responses."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    text = text.strip()
    return text


def _parse_json_safe(text: str):
    """Attempt to parse JSON from potentially messy LLM output."""
    cleaned = _clean_json_response(text)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    for pattern in [
        r"(\[[\s\S]*\])",
        r"(\{[\s\S]*\})",
    ]:
        match = re.search(pattern, cleaned)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                continue

    raise ValueError(f"Could not parse JSON from LLM response:\n{text[:500]}")


class FactCheckAnalyzer:
    """
    Orchestrates the full fact-check pipeline:
    1. Extract claims from document text
    2. Verify each claim against web sources
    3. Compute trust score and generate executive summary
    """

    SYSTEM_PROMPT = (
        "You are FactCheckAI, a rigorous, evidence-based claim verification engine "
        "deployed as a production-grade \"Truth Layer\" for marketing and research "
        "documents. Your purpose is to extract every verifiable claim from a given "
        "document and cross-reference each one against live, authoritative sources — "
        "then produce a structured, auditable verdict for every claim.\n\n"
        "You do not speculate. You do not assume. You only report what evidence "
        "confirms, contradicts, or leaves unresolved.\n\n"
        "OPERATING PRINCIPLES:\n\n"
        "1. OBJECTIVITY FIRST — Never let tone, branding, or persuasive language "
        "influence your verdicts. Treat every claim as a hypothesis to be falsified.\n"
        "2. EVIDENCE HIERARCHY — Prioritize sources in this order:\n"
        "   (a) Official government / regulatory bodies (SEC, WHO, RBI, SEBI, UN, etc.)\n"
        "   (b) Peer-reviewed academic publications\n"
        "   (c) Reputable financial data providers (Bloomberg, Reuters, Statista, World Bank, IMF)\n"
        "   (d) Official company filings (10-K, annual reports, press releases)\n"
        "   (e) Established tier-1 journalism (FT, WSJ, NYT, The Economist)\n"
        "3. RECENCY BIAS — For statistics and figures, always prefer the most recent "
        "authoritative data. Flag anything older than 24 months as potentially outdated.\n"
        "4. ZERO HALLUCINATION POLICY — If you cannot find evidence from a verifiable "
        "source, you MUST return verdict: \"UNVERIFIED\" — never fabricate a supporting citation.\n"
        "5. TRANSPARENCY — Every verdict must include the source URL, publication date, "
        "and a confidence score.\n\n"
        "HARD CONSTRAINTS:\n"
        "- NEVER assign VERIFIED without citing at least one source URL\n"
        "- NEVER assign FALSE based on absence of evidence alone — use UNVERIFIED for that\n"
        "- NEVER cite Wikipedia as a primary source (use it only to identify the correct primary source)\n"
        "- If you cannot find a specific source URL, you MUST return verdict UNVERIFIED"
    )

    EXTRACTION_PROMPT = (
        "Analyze the following document text carefully. Extract ONLY claims that are "
        "objectively verifiable. Do NOT extract opinions, aspirational statements, or "
        "subjective language.\n\n"
        "Claim types to extract:\n"
        "- Statistical claims — percentages, growth rates, market sizes, survey results\n"
        "- Financial figures — revenue, valuation, funding, profit margins\n"
        "- Temporal claims — founding dates, product launch dates, milestone years\n"
        "- Comparative claims — rankings, \"largest\", \"fastest\", \"first\"\n"
        "- Scientific/technical claims — model accuracy, benchmark scores, clinical results\n"
        "- Regulatory/compliance claims — certifications, legal status\n"
        "- Attribution claims — quotes or data attributed to a named source\n\n"
        "Ignore these:\n"
        "- Opinions (\"We believe AI is transformative\")\n"
        "- Future intentions (\"We plan to expand to Europe\")\n"
        "- Vague qualitative statements (\"industry-leading performance\")\n"
        "- Marketing slogans\n\n"
        "Edge cases:\n"
        "- Compound claims (one sentence with two stats): Split into two separate claim IDs\n"
        "- Vague attribution (\"studies show\", \"experts say\"): Extract and note missing attribution\n"
        "- Relative claims (\"grew 3x\"): Extract and note that both baseline and end figure need verification\n\n"
        "CRITICAL: Return ONLY a valid JSON array. No markdown, no commentary, no code fences.\n\n"
        "Return the output as a JSON array where each element has:\n"
        "- \"claim_id\": auto-incremented string like \"C001\", \"C002\", etc.\n"
        "- \"claim_text\": exact verbatim quote from the document\n"
        "- \"claim_type\": one of \"Statistical\", \"Financial\", \"Temporal\", \"Comparative\", "
        "\"Scientific\", \"Regulatory\", \"Attribution\"\n"
        "- \"claim_source_in_doc\": page number or section if available (e.g. \"Page 1\", \"Page 3\"), "
        "or null\n\n"
        "---\n\n"
        "DOCUMENT TEXT:\n\n"
        "{document_text}\n\n"
        "---\n\n"
        "Return ONLY the JSON array. No other text."
    )

    VERIFICATION_PROMPT = (
        "You are verifying the following claim extracted from a document. Use web search "
        "to find authoritative evidence that supports or contradicts this claim.\n\n"
        "CLAIM TO VERIFY:\n"
        "- Claim ID: {claim_id}\n"
        "- Claim Text: \"{claim_text}\"\n"
        "- Claim Type: {claim_type}\n\n"
        "SEARCH STRATEGY:\n"
        "- Use the exact numbers, entities, and dates from the claim as search anchors\n"
        "- Search at least 2-3 independent sources before rendering a verdict\n"
        "- For attributed claims (e.g., \"Gartner says X\"), search for the original report directly\n"
        "- For financial figures, cross-check against official filings or databases\n"
        "- For scientific claims, search Google Scholar, arXiv, or PubMed\n\n"
        "RED FLAGS TO CHECK:\n"
        "- Number matches but year is different (outdated stat presented as current)\n"
        "- Source is real but specific figure is misquoted or misattributed\n"
        "- Statistic exists but context is materially different (e.g., global vs. regional)\n"
        "- Claim cherry-picks a favorable period\n\n"
        "VERDICT OPTIONS:\n"
        "- VERIFIED: Claim matches authoritative source data within plus or minus 5 percent for figures\n"
        "- INACCURATE: Claim is based on real data but the figure, date, or context is materially wrong or outdated\n"
        "- FALSE: Claim directly contradicts authoritative source data\n"
        "- UNVERIFIED: No authoritative source found to confirm or deny\n\n"
        "VERDICT RULES:\n"
        "- If a stat was true in a past year but presented without a year as if current, mark INACCURATE\n"
        "- If the number is fabricated with no traceable origin, mark FALSE\n"
        "- If a real source exists but the number is within 5 percent due to rounding, mark VERIFIED (note variance)\n"
        "- If the source exists but is paywalled and unconfirmable, mark UNVERIFIED\n"
        "- NEVER assign VERIFIED without at least one source URL\n"
        "- NEVER assign FALSE based on absence of evidence — use UNVERIFIED\n\n"
        "CRITICAL: Return ONLY a valid JSON object. No markdown, no commentary, no code fences.\n\n"
        "Return ONLY a JSON object with these fields:\n"
        "- \"claim_id\": \"{claim_id}\"\n"
        "- \"claim_text\": the original claim text\n"
        "- \"claim_type\": \"{claim_type}\"\n"
        "- \"verdict\": one of \"VERIFIED\", \"INACCURATE\", \"FALSE\", \"UNVERIFIED\"\n"
        "- \"correct_fact\": what the actual data says (string), or null if VERIFIED\n"
        "- \"evidence\": array of objects, each with \"source_name\", \"source_url\", "
        "\"publication_date\" (YYYY-MM-DD or null), \"relevant_excerpt\"\n"
        "- \"confidence_score\": one of \"High\", \"Medium\", \"Low\"\n"
        "- \"analyst_note\": any important nuance, caveats, or context (string or null)\n\n"
        "Return ONLY the JSON object. No other text."
    )

    SUMMARY_PROMPT = (
        "Based on the following fact-check results, write a concise 3-5 sentence "
        "executive summary covering:\n\n"
        "1. Overall document trustworthiness (cite the trust score: {trust_score}/100)\n"
        "2. Most critical inaccuracies or false claims found\n"
        "3. Whether the document is suitable for use in professional/public-facing contexts\n"
        "4. Any systemic pattern detected (e.g., \"All financial figures appear outdated\")\n\n"
        "FACT-CHECK RESULTS:\n"
        "- Total claims analyzed: {total_claims}\n"
        "- Verified: {verified_count}\n"
        "- Inaccurate: {inaccurate_count}\n"
        "- False: {false_count}\n"
        "- Unverified: {unverified_count}\n"
        "- Trust Score: {trust_score}/100\n\n"
        "CLAIM DETAILS:\n"
        "{claim_details}\n\n"
        "Write the summary in a professional, objective tone. Be specific about which "
        "claims are problematic.\n"
        "Return ONLY the summary text, no JSON, no markdown headers."
    )

    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-2.5-flash",
    ):
        """
        Initialize the analyzer with a Gemini API key.

        Args:
            api_key: Google Gemini API key.
            model_name: Gemini model to use.
        """
        genai.configure(api_key=api_key)
        self.model_name = model_name
        self.model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=self.SYSTEM_PROMPT,
            generation_config=genai.GenerationConfig(
                temperature=0.1,
                max_output_tokens=8192,
            ),
        )

        self.search_model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=self.SYSTEM_PROMPT,
            generation_config=genai.GenerationConfig(
                temperature=0.1,
                max_output_tokens=4096,
            ),
            tools=[genai.protos.Tool(
                google_search=genai.protos.Tool.GoogleSearch()
            )],
        )

    def extract_claims(self, document_text: str) -> list[Claim]:
        """
        Extract verifiable claims from document text.

        Args:
            document_text: Full text of the document with page markers.

        Returns:
            List of extracted Claim objects.
        """
        prompt = self.EXTRACTION_PROMPT.format(document_text=document_text[:50000])

        response = self.model.generate_content(prompt)
        raw_text = response.text

        claims_data = _parse_json_safe(raw_text)

        if not isinstance(claims_data, list):
            raise ValueError("Expected a JSON array of claims from extraction step.")

        claims: list[Claim] = []
        for i, item in enumerate(claims_data):
            try:
                claim_type_str = item.get("claim_type", "Statistical")
                try:
                    claim_type = ClaimType(claim_type_str)
                except ValueError:
                    claim_type = ClaimType.STATISTICAL

                claim = Claim(
                    claim_id=item.get("claim_id", f"C{i + 1:03d}"),
                    claim_text=item.get("claim_text", ""),
                    claim_type=claim_type,
                    claim_source_in_doc=item.get("claim_source_in_doc"),
                )
                if claim.claim_text.strip():
                    claims.append(claim)
            except Exception:
                continue

        return claims

    def verify_claim(self, claim: Claim) -> ClaimVerdict:
        """
        Verify a single claim using web search grounding.

        Args:
            claim: The Claim object to verify.

        Returns:
            A ClaimVerdict with evidence and verdict.
        """
        prompt = self.VERIFICATION_PROMPT.format(
            claim_id=claim.claim_id,
            claim_text=claim.claim_text,
            claim_type=claim.claim_type.value,
        )

        try:
            response = self.search_model.generate_content(prompt)
            raw_text = response.text
            verdict_data = _parse_json_safe(raw_text)
        except Exception as e:
            try:
                response = self.model.generate_content(prompt)
                raw_text = response.text
                verdict_data = _parse_json_safe(raw_text)
            except Exception:
                return ClaimVerdict(
                    claim_id=claim.claim_id,
                    claim_text=claim.claim_text,
                    claim_type=claim.claim_type,
                    verdict=Verdict.UNVERIFIED,
                    verdict_symbol=VERDICT_SYMBOLS[Verdict.UNVERIFIED],
                    correct_fact=None,
                    evidence=[],
                    confidence_score=ConfidenceLevel.LOW,
                    analyst_note=f"Verification failed due to an error: {e}",
                )

        try:
            verdict_str = verdict_data.get("verdict", "UNVERIFIED").upper()
            try:
                verdict = Verdict(verdict_str)
            except ValueError:
                verdict = Verdict.UNVERIFIED

            confidence_str = verdict_data.get("confidence_score", "Medium")
            try:
                confidence = ConfidenceLevel(confidence_str)
            except ValueError:
                confidence = ConfidenceLevel.MEDIUM

            evidence_list: list[Evidence] = []
            for ev in verdict_data.get("evidence", []):
                try:
                    evidence_list.append(Evidence(
                        source_name=ev.get("source_name", "Unknown"),
                        source_url=ev.get("source_url", ""),
                        publication_date=ev.get("publication_date"),
                        relevant_excerpt=ev.get("relevant_excerpt", ""),
                    ))
                except Exception:
                    continue

            return ClaimVerdict(
                claim_id=claim.claim_id,
                claim_text=claim.claim_text,
                claim_type=claim.claim_type,
                verdict=verdict,
                verdict_symbol=VERDICT_SYMBOLS.get(verdict, ""),
                correct_fact=verdict_data.get("correct_fact"),
                evidence=evidence_list,
                confidence_score=confidence,
                analyst_note=verdict_data.get("analyst_note"),
            )

        except Exception as e:
            return ClaimVerdict(
                claim_id=claim.claim_id,
                claim_text=claim.claim_text,
                claim_type=claim.claim_type,
                verdict=Verdict.UNVERIFIED,
                verdict_symbol=VERDICT_SYMBOLS[Verdict.UNVERIFIED],
                confidence_score=ConfidenceLevel.LOW,
                analyst_note=f"Failed to parse verdict response: {e}",
            )

    def generate_executive_summary(self, report: FactCheckReport) -> str:
        """
        Generate a 3-5 sentence executive summary of the fact-check results.

        Args:
            report: The completed FactCheckReport.

        Returns:
            Executive summary string.
        """
        claim_details_lines = []
        for c in report.claims:
            line = f"- {c.claim_id} [{c.verdict.value}]: \"{c.claim_text[:100]}\""
            if c.correct_fact:
                line += f" -> Actual: {c.correct_fact[:100]}"
            claim_details_lines.append(line)

        prompt = self.SUMMARY_PROMPT.format(
            trust_score=report.overall_trust_score,
            total_claims=report.total_claims_extracted,
            verified_count=report.verdict_summary.VERIFIED,
            inaccurate_count=report.verdict_summary.INACCURATE,
            false_count=report.verdict_summary.FALSE,
            unverified_count=report.verdict_summary.UNVERIFIED,
            claim_details="\n".join(claim_details_lines),
        )

        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception:
            return (
                f"This document received a trust score of "
                f"{report.overall_trust_score}/100 based on analysis of "
                f"{report.total_claims_extracted} verifiable claims. "
                f"Automated summary generation encountered an error."
            )

    def run_full_pipeline(
        self,
        pdf_text: str,
        document_title: str = "Untitled Document",
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> FactCheckReport:
        """
        Run the complete fact-check pipeline.

        Args:
            pdf_text: Extracted text from the PDF (with page markers).
            document_title: Title of the document being analyzed.
            progress_callback: Optional callback(status_message, progress_fraction)
                for real-time UI updates.

        Returns:
            A complete FactCheckReport.
        """
        report = FactCheckReport(document_title=document_title)

        if progress_callback:
            progress_callback("Extracting verifiable claims from document...", 0.1)

        claims = self.extract_claims(pdf_text)

        if not claims:
            report.executive_summary = (
                "No verifiable claims were found in this document. "
                "The document may contain only opinions, future intentions, "
                "or vague qualitative statements."
            )
            if progress_callback:
                progress_callback("No verifiable claims found.", 1.0)
            return report

        if len(claims) < 3:
            note = (
                f"Note: Only {len(claims)} verifiable claim(s) found. "
                "The document contains fewer than 3 verifiable claims, "
                "which limits the reliability of the overall trust score."
            )
        else:
            note = ""

        if progress_callback:
            progress_callback(
                f"Found {len(claims)} verifiable claims. Starting verification...",
                0.2,
            )

        verdicts: list[ClaimVerdict] = []
        for i, claim in enumerate(claims):
            if progress_callback:
                frac = 0.2 + (0.6 * (i / len(claims)))
                progress_callback(
                    f"Verifying claim {i + 1}/{len(claims)}: "
                    f"{claim.claim_text[:60]}...",
                    frac,
                )

            verdict = self.verify_claim(claim)
            verdicts.append(verdict)

            if i < len(claims) - 1:
                time.sleep(0.5)

        if progress_callback:
            progress_callback("Computing trust score and assembling report...", 0.85)

        report.claims = verdicts
        report.compute_verdict_summary()
        report.compute_trust_score()

        if progress_callback:
            progress_callback("Generating executive summary...", 0.92)

        summary = self.generate_executive_summary(report)
        if note:
            summary = note + "\n\n" + summary
        report.executive_summary = summary

        if progress_callback:
            progress_callback("Analysis complete!", 1.0)

        return report
