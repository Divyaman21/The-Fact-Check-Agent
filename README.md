# 🔬 FactCheck Agent

**AI-Powered Claim Verification Engine** — A production-grade Streamlit application that extracts, verifies, and scores every factual claim in your documents against live web sources.

## Features

- 📄 **PDF Upload** — Drag-and-drop PDF processing with PyMuPDF
- 🔍 **Claim Extraction** — AI identifies statistical, financial, temporal, comparative, scientific, regulatory, and attribution claims
- 🌐 **Web Verification** — Each claim cross-referenced against authoritative web sources using Google Search grounding
- 📊 **Trust Score** — Weighted scoring system (0-100) with per-verdict penalties
- 📋 **Structured Reports** — JSON export, CSV tables, and AI-generated executive summaries
- 🎨 **Premium UI** — Dark-themed dashboard with glassmorphism, animations, and rich data visualization

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API Key

Get a free Gemini API key at [https://aistudio.google.com/apikey](https://aistudio.google.com/apikey).

Either create a `.env` file:
```bash
cp .env.example .env
# Edit .env and add your key
```

Or enter it directly in the app sidebar.

### 3. Run the App

```bash
streamlit run app.py
```

## Architecture

```
PDF Upload
    ↓
Text Extraction (PyMuPDF)
    ↓
Claim Extraction (Gemini LLM — Step 1)
    ↓
Per-Claim Web Verification (Gemini + Google Search — Steps 2-3)
    ↓
Trust Score Computation (Step 4)
    ↓
Executive Summary Generation (Step 5)
    ↓
Interactive Dashboard + JSON/CSV Export
```

## Project Structure

```
cogculture/
├── app.py                    # Streamlit application
├── factcheck/
│   ├── __init__.py
│   ├── models.py             # Pydantic data models
│   ├── extractor.py          # PDF text extraction
│   ├── analyzer.py           # LLM claim verification engine
│   └── prompts.py            # System prompts
├── .streamlit/
│   └── config.toml           # Theme configuration
├── requirements.txt
├── .env.example
└── factcheck_agent_prompt.md # Master prompt specification
```

## Verdict System

| Verdict | Symbol | Penalty | Definition |
|---------|--------|---------|------------|
| VERIFIED | ✅ | 0 pts | Matches authoritative source (±5%) |
| INACCURATE | ⚠️ | -5 pts | Real data, but wrong/outdated figure |
| FALSE | ❌ | -10 pts | Contradicts authoritative sources |
| UNVERIFIED | 🔍 | -2 pts | No source found to confirm or deny |

> Trust score starts at 100. Capped at 80 if any claim is FALSE.

---

*Built for CogCulture Assessment, Part 2*
