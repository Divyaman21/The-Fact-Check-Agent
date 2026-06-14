"""
FactCheck Agent — Streamlit Application
A production-grade claim verification dashboard for marketing and research documents.
"""

import json
import os
import time
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

from factcheck.extractor import extract_text_from_pdf, get_pdf_metadata
from factcheck.analyzer import FactCheckAnalyzer
from factcheck.models import FactCheckReport, Verdict

load_dotenv()

st.set_page_config(
    page_title="FactCheck Agent — AI-Powered Claim Verification",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.html("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

    html, body, .stApp, .main, .block-container, p, span, li, td, th, label, div {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }

    .stApp {
        background: linear-gradient(160deg, rgb(15, 15, 26) 0%, rgb(13, 13, 31) 40%, rgb(18, 16, 31) 100%) !important;
    }

    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 3rem !important;
        max-width: 1200px !important;
    }

    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: rgb(55, 48, 163); border-radius: 3px; }

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, rgb(15, 15, 26) 0%, rgb(21, 21, 40) 100%) !important;
        border-right: 1px solid rgba(124, 58, 237, 0.15) !important;
    }

    section[data-testid="stSidebar"] .stTextInput > div > div > input {
        background: rgba(124, 58, 237, 0.08) !important;
        border: 1px solid rgba(124, 58, 237, 0.25) !important;
        color: rgb(226, 232, 240) !important;
        border-radius: 8px !important;
    }

    .hero-header {
        background: linear-gradient(135deg, rgba(124, 58, 237, 0.15) 0%, rgba(59, 130, 246, 0.10) 50%, rgba(139, 92, 246, 0.12) 100%);
        border: 1px solid rgba(124, 58, 237, 0.2);
        border-radius: 16px;
        padding: 2.5rem 2rem;
        margin-bottom: 2rem;
        position: relative;
        overflow: hidden;
    }

    .hero-header::before {
        content: '';
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: radial-gradient(circle at 30% 50%, rgba(124, 58, 237, 0.06) 0%, transparent 60%);
        animation: heroGlow 8s ease-in-out infinite;
    }

    @keyframes heroGlow {
        0%, 100% { transform: translate(0, 0); }
        50% { transform: translate(5%, 3%); }
    }

    .hero-title {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(135deg, rgb(196, 181, 253) 0%, rgb(129, 140, 248) 40%, rgb(96, 165, 250) 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 0 0 0.5rem 0;
        position: relative;
        letter-spacing: -0.02em;
    }

    .hero-subtitle {
        color: rgb(148, 163, 184);
        font-size: 1.05rem;
        font-weight: 400;
        margin: 0;
        position: relative;
        line-height: 1.6;
    }

    .upload-zone {
        background: linear-gradient(135deg, rgba(124, 58, 237, 0.06) 0%, rgba(59, 130, 246, 0.04) 100%);
        border: 2px dashed rgba(124, 58, 237, 0.3);
        border-radius: 16px;
        padding: 3rem 2rem;
        text-align: center;
        transition: all 0.3s ease;
        margin: 1rem 0;
    }

    .upload-zone:hover {
        border-color: rgba(124, 58, 237, 0.6);
        background: linear-gradient(135deg, rgba(124, 58, 237, 0.10) 0%, rgba(59, 130, 246, 0.07) 100%);
    }

    .upload-icon {
        font-size: 3rem;
        margin-bottom: 0.5rem;
        animation: float 3s ease-in-out infinite;
    }

    @keyframes float {
        0%, 100% { transform: translateY(0px); }
        50% { transform: translateY(-8px); }
    }

    .metric-card {
        background: rgba(26, 26, 46, 0.8);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(124, 58, 237, 0.15);
        border-radius: 14px;
        padding: 1.5rem;
        text-align: center;
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
    }

    .metric-card:hover {
        border-color: rgba(124, 58, 237, 0.4);
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(124, 58, 237, 0.12);
    }

    .metric-card .metric-value {
        font-size: 2.2rem;
        font-weight: 800;
        margin: 0.25rem 0;
        line-height: 1;
    }

    .metric-card .metric-label {
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: rgb(148, 163, 184);
        margin-bottom: 0.25rem;
    }

    .metric-card .metric-icon {
        font-size: 1.5rem;
        margin-bottom: 0.25rem;
    }

    .metric-verified { border-top: 3px solid rgb(52, 211, 153); }
    .metric-verified .metric-value { color: rgb(52, 211, 153); }

    .metric-inaccurate { border-top: 3px solid rgb(251, 191, 36); }
    .metric-inaccurate .metric-value { color: rgb(251, 191, 36); }

    .metric-false { border-top: 3px solid rgb(248, 113, 113); }
    .metric-false .metric-value { color: rgb(248, 113, 113); }

    .metric-unverified { border-top: 3px solid rgb(96, 165, 250); }
    .metric-unverified .metric-value { color: rgb(96, 165, 250); }

    .trust-gauge {
        background: rgba(26, 26, 46, 0.8);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(124, 58, 237, 0.2);
        border-radius: 16px;
        padding: 2rem;
        text-align: center;
        position: relative;
    }

    .trust-score-circle {
        width: 160px;
        height: 160px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 auto 1rem;
        position: relative;
    }

    .trust-score-value {
        font-size: 3rem;
        font-weight: 900;
        letter-spacing: -0.03em;
    }

    .trust-score-label {
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: rgb(148, 163, 184);
    }

    .trust-high .trust-score-circle {
        background: conic-gradient(rgb(52, 211, 153) var(--score-pct), rgba(52, 211, 153, 0.1) 0);
    }
    .trust-high .trust-score-value { color: rgb(52, 211, 153); }

    .trust-medium .trust-score-circle {
        background: conic-gradient(rgb(251, 191, 36) var(--score-pct), rgba(251, 191, 36, 0.1) 0);
    }
    .trust-medium .trust-score-value { color: rgb(251, 191, 36); }

    .trust-low .trust-score-circle {
        background: conic-gradient(rgb(248, 113, 113) var(--score-pct), rgba(248, 113, 113, 0.1) 0);
    }
    .trust-low .trust-score-value { color: rgb(248, 113, 113); }

    .trust-score-inner {
        width: 130px;
        height: 130px;
        border-radius: 50%;
        background: rgb(19, 19, 31);
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
    }

    .claim-card {
        background: rgba(26, 26, 46, 0.6);
        backdrop-filter: blur(8px);
        border: 1px solid rgba(124, 58, 237, 0.12);
        border-radius: 12px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 0.75rem;
        transition: all 0.25s ease;
    }

    .claim-card:hover {
        border-color: rgba(124, 58, 237, 0.3);
        background: rgba(26, 26, 46, 0.8);
    }

    .claim-header {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin-bottom: 0.5rem;
    }

    .claim-id {
        background: rgba(124, 58, 237, 0.2);
        color: rgb(196, 181, 253);
        padding: 0.2rem 0.6rem;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.05em;
    }

    .verdict-badge {
        padding: 0.2rem 0.75rem;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.03em;
    }

    .verdict-verified {
        background: rgba(52, 211, 153, 0.15);
        color: rgb(52, 211, 153);
        border: 1px solid rgba(52, 211, 153, 0.3);
    }
    .verdict-inaccurate {
        background: rgba(251, 191, 36, 0.15);
        color: rgb(251, 191, 36);
        border: 1px solid rgba(251, 191, 36, 0.3);
    }
    .verdict-false {
        background: rgba(248, 113, 113, 0.15);
        color: rgb(248, 113, 113);
        border: 1px solid rgba(248, 113, 113, 0.3);
    }
    .verdict-unverified {
        background: rgba(96, 165, 250, 0.15);
        color: rgb(96, 165, 250);
        border: 1px solid rgba(96, 165, 250, 0.3);
    }

    .confidence-pill {
        padding: 0.15rem 0.5rem;
        border-radius: 10px;
        font-size: 0.7rem;
        font-weight: 600;
        background: rgba(148, 163, 184, 0.1);
        color: rgb(148, 163, 184);
        border: 1px solid rgba(148, 163, 184, 0.2);
        margin-left: auto;
    }

    .claim-text {
        color: rgb(203, 213, 225);
        font-size: 0.92rem;
        line-height: 1.5;
        margin: 0.5rem 0;
    }

    .claim-type-tag {
        display: inline-block;
        background: rgba(124, 58, 237, 0.1);
        color: rgb(167, 139, 250);
        padding: 0.15rem 0.5rem;
        border-radius: 6px;
        font-size: 0.7rem;
        font-weight: 600;
        margin-left: 0.5rem;
    }

    .correct-fact {
        background: rgba(251, 191, 36, 0.06);
        border-left: 3px solid rgb(251, 191, 36);
        padding: 0.75rem 1rem;
        border-radius: 0 8px 8px 0;
        margin: 0.75rem 0;
        color: rgb(253, 230, 138);
        font-size: 0.85rem;
    }

    .evidence-item {
        background: rgba(59, 130, 246, 0.05);
        border: 1px solid rgba(59, 130, 246, 0.12);
        border-radius: 8px;
        padding: 0.75rem 1rem;
        margin: 0.4rem 0;
        font-size: 0.83rem;
    }

    .evidence-item a {
        color: rgb(96, 165, 250) !important;
        text-decoration: none;
    }

    .evidence-item a:hover {
        text-decoration: underline;
    }

    .analyst-note {
        background: rgba(139, 92, 246, 0.06);
        border-left: 3px solid rgb(139, 92, 246);
        padding: 0.75rem 1rem;
        border-radius: 0 8px 8px 0;
        margin-top: 0.75rem;
        color: rgb(196, 181, 253);
        font-size: 0.85rem;
        font-style: italic;
    }

    .exec-summary {
        background: linear-gradient(135deg, rgba(124, 58, 237, 0.08) 0%, rgba(59, 130, 246, 0.05) 100%);
        border: 1px solid rgba(124, 58, 237, 0.2);
        border-radius: 14px;
        padding: 1.75rem;
        margin: 1.5rem 0;
        line-height: 1.7;
        color: rgb(203, 213, 225);
        font-size: 0.95rem;
    }

    .pipeline-step {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding: 0.6rem 0;
        color: rgb(148, 163, 184);
        font-size: 0.9rem;
    }

    .pipeline-step.active {
        color: rgb(196, 181, 253);
    }

    .pipeline-step.done {
        color: rgb(52, 211, 153);
    }

    .step-indicator {
        width: 28px;
        height: 28px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.75rem;
        font-weight: 700;
        flex-shrink: 0;
    }

    .step-pending .step-indicator {
        background: rgba(148, 163, 184, 0.1);
        border: 2px solid rgba(148, 163, 184, 0.3);
        color: rgb(100, 116, 139);
    }

    .step-active .step-indicator {
        background: rgba(124, 58, 237, 0.2);
        border: 2px solid rgb(124, 58, 237);
        color: rgb(196, 181, 253);
        animation: pulse 2s ease-in-out infinite;
    }

    .step-done .step-indicator {
        background: rgba(52, 211, 153, 0.2);
        border: 2px solid rgb(52, 211, 153);
        color: rgb(52, 211, 153);
    }

    @keyframes pulse {
        0%, 100% { box-shadow: 0 0 0 0 rgba(124, 58, 237, 0.4); }
        50% { box-shadow: 0 0 0 8px rgba(124, 58, 237, 0); }
    }

    .section-title {
        font-size: 1.3rem;
        font-weight: 700;
        color: rgb(226, 232, 240);
        margin: 2rem 0 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid rgba(124, 58, 237, 0.15);
    }

    .file-info {
        background: rgba(26, 26, 46, 0.6);
        border: 1px solid rgba(124, 58, 237, 0.15);
        border-radius: 12px;
        padding: 1rem 1.25rem;
        margin: 1rem 0;
    }

    .file-info-row {
        display: flex;
        justify-content: space-between;
        padding: 0.3rem 0;
        font-size: 0.85rem;
    }

    .file-info-label { color: rgb(100, 116, 139); font-weight: 500; }
    .file-info-value { color: rgb(203, 213, 225); font-weight: 600; }

    .stButton > button {
        border-radius: 10px !important;
        font-weight: 600 !important;
        font-family: 'Inter', sans-serif !important;
        letter-spacing: 0.02em !important;
        transition: all 0.3s ease !important;
    }

    div.stButton > button:first-child {
        background: linear-gradient(135deg, rgb(124, 58, 237) 0%, rgb(109, 40, 217) 100%) !important;
        color: white !important;
        border: none !important;
        padding: 0.6rem 2rem !important;
    }

    div.stButton > button:first-child:hover {
        background: linear-gradient(135deg, rgb(139, 92, 246) 0%, rgb(124, 58, 237) 100%) !important;
        box-shadow: 0 4px 16px rgba(124, 58, 237, 0.35) !important;
        transform: translateY(-1px) !important;
    }

    .streamlit-expanderHeader {
        font-family: 'Inter', sans-serif !important;
        font-weight: 600 !important;
        color: rgb(196, 181, 253) !important;
        background: transparent !important;
    }

    hr {
        border-color: rgba(124, 58, 237, 0.1) !important;
        margin: 1.5rem 0 !important;
    }

    .stDownloadButton > button {
        background: rgba(124, 58, 237, 0.15) !important;
        color: rgb(196, 181, 253) !important;
        border: 1px solid rgba(124, 58, 237, 0.3) !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
    }

    .stDownloadButton > button:hover {
        background: rgba(124, 58, 237, 0.25) !important;
        border-color: rgba(124, 58, 237, 0.5) !important;
    }

    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, rgb(124, 58, 237), rgb(109, 40, 217), rgb(129, 140, 248)) !important;
    }
</style>
""")

if "report" not in st.session_state:
    st.session_state.report = None
if "pdf_text" not in st.session_state:
    st.session_state.pdf_text = None
if "pdf_metadata" not in st.session_state:
    st.session_state.pdf_metadata = None
if "analysis_running" not in st.session_state:
    st.session_state.analysis_running = False
if "status_message" not in st.session_state:
    st.session_state.status_message = ""
if "progress" not in st.session_state:
    st.session_state.progress = 0.0

with st.sidebar:
    st.html("""
        <div style="text-align: center; padding: 1rem 0 1.5rem;">
            <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">🔬</div>
            <div style="font-size: 1.2rem; font-weight: 800;
                 background: linear-gradient(135deg, rgb(196, 181, 253) 0%, rgb(129, 140, 248) 100%);
                 -webkit-background-clip: text; -webkit-text-fill-color: transparent;
                 background-clip: text;">FactCheck Agent</div>
            <div style="color: rgb(100, 116, 139); font-size: 0.75rem; margin-top: 0.25rem;
                 font-weight: 500; letter-spacing: 0.05em;">
                AI-POWERED VERIFICATION ENGINE
            </div>
        </div>
    """)

    st.divider()

    st.markdown("API Configuration")
    api_key = st.text_input(
        "Gemini API Key",
        type="password",
        value=os.environ.get("GOOGLE_API_KEY") or (st.secrets["GOOGLE_API_KEY"] if "GOOGLE_API_KEY" in st.secrets else "") or "",
        help="Get your key at https://aistudio.google.com/apikey",
        placeholder="Enter your Gemini API key...",
    )

    model_choice = st.selectbox(
        "Model",
        options=["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"],
        index=0,
        help="Select the Gemini model for analysis.",
    )

    st.divider()

    with st.expander("Methodology", expanded=False):
        st.markdown("""
        FactCheck Agent follows a 5-step pipeline:

        1. Extract - PDF text extraction via PyMuPDF
        2. Identify - LLM extracts verifiable claims
        3. Verify - Each claim checked against web sources
        4. Score - Trust score computed per verdict weights
        5. Report - Structured JSON + executive summary

        Verdict Weights:
        - FALSE: -10 points
        - INACCURATE: -5 points
        - UNVERIFIED: -2 points
        - VERIFIED: 0 points

        Trust score starts at 100, capped at 80 if any FALSE claim exists.
        """)

    st.divider()

    st.html("""
        <div style="text-align: center; color: rgb(71, 85, 105); font-size: 0.7rem;
             padding: 0.5rem 0; line-height: 1.6;">
            Built for CogCulture Assessment<br>
            <span style="color: rgb(100, 116, 139); font-weight: 600;">v1.0</span>
        </div>
    """)


def render_trust_gauge(score: int):
    if score >= 80:
        trust_class = "trust-high"
    elif score >= 50:
        trust_class = "trust-medium"
    else:
        trust_class = "trust-low"

    st.html(f"""
        <div class="trust-gauge {trust_class}" style="--score-pct: {score}%;">
            <div class="trust-score-circle">
                <div class="trust-score-inner">
                    <div class="trust-score-value">{score}</div>
                    <div style="color: rgb(100, 116, 139); font-size: 0.7rem; font-weight: 600;">/100</div>
                </div>
            </div>
            <div class="trust-score-label">Overall Trust Score</div>
        </div>
    """)


def render_verdict_badge(verdict: Verdict) -> str:
    configs = {
        Verdict.VERIFIED: ("VERIFIED", "verdict-verified"),
        Verdict.INACCURATE: ("INACCURATE", "verdict-inaccurate"),
        Verdict.FALSE: ("FALSE", "verdict-false"),
        Verdict.UNVERIFIED: ("UNVERIFIED", "verdict-unverified"),
    }
    label, css_class = configs.get(verdict, ("UNKNOWN", "verdict-unverified"))
    return f'<span class="verdict-badge {css_class}">{label}</span>'


def render_claim_card(claim):
    verdict_html = render_verdict_badge(claim.verdict)

    evidence_html = ""
    if claim.evidence:
        for ev in claim.evidence:
            url_html = f'<a href="{ev.source_url}" target="_blank">{ev.source_name}</a>' if ev.source_url else ev.source_name
            date_html = f' · {ev.publication_date}' if ev.publication_date else ""
            evidence_html += f"""
                <div class="evidence-item">
                    <strong>{url_html}</strong>{date_html}<br>
                    <span style="color: rgb(148, 163, 184);">{ev.relevant_excerpt}</span>
                </div>
            """

    correct_fact_html = ""
    if claim.correct_fact:
        correct_fact_html = f"""
            <div class="correct-fact">
                <strong>Correct Fact:</strong> {claim.correct_fact}
            </div>
        """

    analyst_note_html = ""
    if claim.analyst_note:
        analyst_note_html = f"""
            <div class="analyst-note">
                <strong>Analyst Note:</strong> {claim.analyst_note}
            </div>
        """

    st.html(f"""
        <div class="claim-card">
            <div class="claim-header">
                <span class="claim-id">{claim.claim_id}</span>
                {verdict_html}
                <span class="claim-type-tag">{claim.claim_type.value if hasattr(claim.claim_type, 'value') else claim.claim_type}</span>
                <span class="confidence-pill">{claim.confidence_score.value if hasattr(claim.confidence_score, 'value') else claim.confidence_score} confidence</span>
            </div>
            <div class="claim-text">"{claim.claim_text}"</div>
            {correct_fact_html}
            {evidence_html}
            {analyst_note_html}
        </div>
    """)


st.html("""
    <div class="hero-header">
        <h1 class="hero-title">FactCheck Agent</h1>
        <p class="hero-subtitle">
            Upload a PDF document and let AI extract, verify, and score every factual claim
            against live web sources. Powered by rigorous evidence-based methodology.
        </p>
    </div>
""")

if st.session_state.report is None and not st.session_state.analysis_running:

    st.html("""
        <div class="upload-zone">
            <div class="upload-icon">📄</div>
            <div style="color: rgb(196, 181, 253); font-size: 1.1rem; font-weight: 600; margin-bottom: 0.25rem;">
                Upload your document
            </div>
            <div style="color: rgb(100, 116, 139); font-size: 0.85rem;">
                PDF files supported · Text-based documents only
            </div>
        </div>
    """)

    uploaded_file = st.file_uploader(
        "Upload a PDF",
        type=["pdf"],
        label_visibility="collapsed",
        help="Upload a PDF document to analyze for factual claims.",
    )

    if uploaded_file is not None:
        pdf_bytes = uploaded_file.read()

        try:
            pdf_text, page_count = extract_text_from_pdf(pdf_bytes)
            metadata = get_pdf_metadata(pdf_bytes)
            st.session_state.pdf_text = pdf_text
            st.session_state.pdf_metadata = metadata

            st.html(f"""
                <div class="file-info">
                    <div class="file-info-row">
                        <span class="file-info-label">File</span>
                        <span class="file-info-value">{uploaded_file.name}</span>
                    </div>
                    <div class="file-info-row">
                        <span class="file-info-label">Pages</span>
                        <span class="file-info-value">{metadata.get('page_count', 'N/A')}</span>
                    </div>
                    <div class="file-info-row">
                        <span class="file-info-label">Size</span>
                        <span class="file-info-value">{metadata.get('file_size_kb', 'N/A')} KB</span>
                    </div>
                    <div class="file-info-row">
                        <span class="file-info-label">Title</span>
                        <span class="file-info-value">{metadata.get('title', 'Untitled')}</span>
                    </div>
                </div>
            """)

            with st.expander("Extracted Text Preview", expanded=False):
                st.text(pdf_text[:3000] + ("..." if len(pdf_text) > 3000 else ""))

            if not api_key:
                st.warning("Please enter your Gemini API key in the sidebar to begin analysis.")
            else:
                if st.button("Analyze Document", use_container_width=True):
                    st.session_state.analysis_running = True
                    st.rerun()

        except ValueError as e:
            st.error(f"{e}")
        except Exception as e:
            st.error(f"An unexpected error occurred: {e}")

elif st.session_state.analysis_running and st.session_state.report is None:
    st.html('<div class="section-title">Analysis in Progress</div>')

    progress_bar = st.progress(0)
    status_text = st.empty()

    steps_container = st.container()

    def update_progress(message: str, fraction: float):
        progress_bar.progress(min(fraction, 1.0))
        status_text.markdown(f"**{message}**")

    try:
        analyzer = FactCheckAnalyzer(
            api_key=api_key,
            model_name=model_choice,
        )

        report = analyzer.run_full_pipeline(
            pdf_text=st.session_state.pdf_text,
            document_title=st.session_state.pdf_metadata.get("title", "Untitled Document"),
            progress_callback=update_progress,
        )

        st.session_state.report = report
        st.session_state.analysis_running = False
        time.sleep(0.5)
        st.rerun()

    except Exception as e:
        st.session_state.analysis_running = False
        st.error(f"Analysis failed: {e}")
        if st.button("Try Again"):
            st.rerun()

elif st.session_state.report is not None:
    report = st.session_state.report

    col_score, col_metrics = st.columns([1, 2])

    with col_score:
        render_trust_gauge(report.overall_trust_score)

    with col_metrics:
        st.html('<div style="margin-bottom: 0.5rem;"></div>')
        m1, m2, m3, m4 = st.columns(4)

        with m1:
            st.html(f"""
                <div class="metric-card metric-verified">
                    <div class="metric-icon">✅</div>
                    <div class="metric-value">{report.verdict_summary.VERIFIED}</div>
                    <div class="metric-label">Verified</div>
                </div>
            """)

        with m2:
            st.html(f"""
                <div class="metric-card metric-inaccurate">
                    <div class="metric-icon">⚠️</div>
                    <div class="metric-value">{report.verdict_summary.INACCURATE}</div>
                    <div class="metric-label">Inaccurate</div>
                </div>
            """)

        with m3:
            st.html(f"""
                <div class="metric-card metric-false">
                    <div class="metric-icon">❌</div>
                    <div class="metric-value">{report.verdict_summary.FALSE}</div>
                    <div class="metric-label">False</div>
                </div>
            """)

        with m4:
            st.html(f"""
                <div class="metric-card metric-unverified">
                    <div class="metric-icon">🔍</div>
                    <div class="metric-value">{report.verdict_summary.UNVERIFIED}</div>
                    <div class="metric-label">Unverified</div>
                </div>
            """)

        st.html(f"""
            <div style="display: flex; gap: 2rem; margin-top: 1rem; padding: 0.5rem 0;
                        color: rgb(100, 116, 139); font-size: 0.8rem;">
                <span>File: <strong style="color: rgb(148, 163, 184);">{report.document_title}</strong></span>
                <span>Time: {report.analysis_timestamp[:19].replace('T', ' ')}</span>
                <span>Count: {report.total_claims_extracted} claims analyzed</span>
            </div>
        """)

    st.divider()

    st.html('<div class="section-title">Executive Summary</div>')
    st.html(f"""
        <div class="exec-summary">
            {report.executive_summary.replace(chr(10), '<br>')}
        </div>
    """)

    st.html(f'<div class="section-title">Detailed Claim Analysis ({report.total_claims_extracted} claims)</div>')

    filter_col1, filter_col2 = st.columns([1, 3])
    with filter_col1:
        verdict_filter = st.selectbox(
            "Filter by verdict",
            options=["All", "VERIFIED", "INACCURATE", "FALSE", "UNVERIFIED"],
            index=0,
        )

    filtered_claims = report.claims
    if verdict_filter != "All":
        filtered_claims = [c for c in report.claims if c.verdict.value == verdict_filter]

    if not filtered_claims:
        st.info("No claims match the selected filter.")
    else:
        for claim in filtered_claims:
            render_claim_card(claim)

    st.divider()

    st.html('<div class="section-title">Export Report</div>')

    export_col1, export_col2, export_col3 = st.columns(3)

    with export_col1:
        report_json = report.model_dump_json(indent=2)
        st.download_button(
            label="Download JSON Report",
            data=report_json,
            file_name=f"factcheck_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True,
        )

    with export_col2:
        csv_lines = ["Claim ID,Claim Text,Type,Verdict,Confidence,Correct Fact"]
        for c in report.claims:
            claim_text_escaped = c.claim_text.replace('"', '""')
            correct_fact_escaped = (c.correct_fact or "—").replace('"', '""')
            csv_lines.append(
                f'"{c.claim_id}","{claim_text_escaped}","{c.claim_type.value if hasattr(c.claim_type, "value") else c.claim_type}","{c.verdict.value}","{c.confidence_score.value if hasattr(c.confidence_score, "value") else c.confidence_score}","{correct_fact_escaped}"'
            )
        csv_data = "\n".join(csv_lines)
        st.download_button(
            label="Download CSV Table",
            data=csv_data,
            file_name=f"factcheck_claims_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with export_col3:
        if st.button("Analyze Another Document", use_container_width=True):
            st.session_state.report = None
            st.session_state.pdf_text = None
            st.session_state.pdf_metadata = None
            st.session_state.analysis_running = False
            st.rerun()
