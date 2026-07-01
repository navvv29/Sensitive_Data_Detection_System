# Architecture — Sensitive Data Detection & Compliance Assistant

## System Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Streamlit UI                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │  Upload   │  │  Results  │  │  Summary  │  │  Q&A   │ │
│  │  Panel    │  │  Display  │  │  Panel    │  │  Chat  │ │
│  └────┬─────┘  └────▲─────┘  └────▲─────┘  └───▲────┘ │
└───────┼──────────────┼────────────┼─────────────┼──────┘
        │              │            │             │
        ▼              │            │             │
┌──────────────┐       │            │             │
│  Extractors  │       │            │             │
│  PDF/TXT/CSV │       │            │             │
└──────┬───────┘       │            │             │
       │               │            │             │
       ▼               │            │             │
┌──────────────┐       │            │             │
│  Detectors   │───────┘            │             │
│  Regex + NLP │────────────────────┤             │
└──────┬───────┘                    │             │
       │                            │             │
       ▼                            │             │
┌──────────────┐                    │             │
│  Classifier  │                    │             │
│  Risk Engine │────────────────────┘             │
└──────┬───────┘                                  │
       │                                          │
       ▼                                          │
┌──────────────┐     ┌──────────────┐             │
│  Summarizer  │     │  RAG Engine  │─────────────┘
│  LLM Client  │     │  ChromaDB +  │
│  Gemini/OAI  │     │  Embeddings  │
└──────────────┘     └──────────────┘
```

## Data Flow

1. **Upload** → User uploads PDF/TXT/CSV via Streamlit
2. **Extract** → Appropriate extractor parses raw text with page/line/row tracking
3. **Detect** → Unified detector runs regex + NLP pipeline over extracted text
4. **Classify** → Risk engine applies weighted scoring to detection results
5. **Summarize** → LLM generates compliance summary grounded in detection data
6. **Q&A** → Document is chunked, embedded, and stored in vector DB for retrieval-augmented QA

## Privacy-by-Design

- Sensitive values are **masked** at the detection layer before any UI rendering
- Logs never contain plaintext PII
- Uploaded files are stored only in memory (not persisted to disk by default)
- API calls to LLM never include raw sensitive values — only masked/anonymized context

## Module Responsibilities

| Module | Responsibility | Key Files |
|--------|---------------|-----------|
| `extractors/` | Parse documents into structured text | `pdf_extractor.py`, `txt_extractor.py`, `csv_extractor.py` |
| `detectors/` | Find sensitive data entities | `regex_detector.py`, `nlp_detector.py`, `unified_detector.py` |
| `classifiers/` | Score and classify risk level | `risk_classifier.py` |
| `summarizers/` | Generate AI compliance summaries | `llm_client.py`, `compliance_summary.py` |
| `rag/` | RAG pipeline for Q&A | `chunker.py`, `embedder.py`, `retriever.py`, `qa_engine.py` |
| `app/` | Streamlit UI wiring | `main.py` |
