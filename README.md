# Sensitive Data Detection & Compliance Assistant

An AI-powered document analysis tool designed to detect sensitive data, classify risk, and generate compliance guidance. Built with Python, Streamlit, spaCy, ChromaDB, and Google Gemini.

## 🔗 Working Prototype Deployment Link (MANDATORY)
[Working Prototype Deployment Link](https://sensitive-data-detection-system.streamlit.app) *(Note: Placeholder link for deployment)*

## 🚀 Features

1. **Multi-Format Extraction**: Reliable text extraction from PDF, TXT, and CSV files, including robust error handling and encoding fallbacks.
2. **Hybrid Detection Engine**:
   - **Regex Patterns**: High-precision detection of structured PII (Aadhaar, PAN, Credit Cards, Phones, API Keys, etc.).
   - **NLP (spaCy NER)**: Contextual detection of names, organizations, and business-sensitive markers.
3. **Privacy-by-Design**: Raw sensitive values are masked before they are exposed to the UI or downstream LLM components.
4. **Explainable Risk Classification**: Weighted scoring system to classify documents as LOW, MEDIUM, or HIGH risk, detailing the exact factors contributing to the score.
5. **AI Compliance Summary**: Generates compliance and security guidance (e.g., DPDP Act, PCI-DSS implications) using LLMs, with a built-in template fallback if API keys are unavailable.
6. **RAG Q&A Engine**: Ask natural language questions about the uploaded document, backed by vector retrieval (ChromaDB) and generative AI, or precise structured counting logic.
7. **CSV Export**: Instantly export a report of masked detected entities.

## 🏗️ Architecture Overview (MANDATORY)

The project follows a modular, loop-engineered architecture:

- `app/` - Streamlit UI layer integrating all components.
- `extractors/` - Format-specific parsers (PDF, TXT, CSV).
- `detectors/` - Regex and NLP engines with a unified pipeline.
- `classifiers/` - Weighted risk scoring logic.
- `summarizers/` - LLM clients and grounded prompt builders.
- `rag/` - Text chunker and QA routing logic.
- `tests/` - Comprehensive 100+ test suite ensuring robustness.

## ⚙️ Setup Instructions (MANDATORY)

### Prerequisites
- Python 3.11+
- pip

### Installation

1. Clone this repository and navigate to the root directory.
2. Create and activate a virtual environment (recommended):
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Download the required spaCy model:
   ```bash
   python -m spacy download en_core_web_sm
   ```

### Configuration

Copy the example environment file and configure your API keys:
```bash
cp .env.example .env
```
Add your `GEMINI_API_KEY` (or `OPENAI_API_KEY`) to the `.env` file to enable AI-generated summaries and Q&A. If no key is provided, the application will still function fully using local extraction, regex/NLP detection, algorithmic risk classification, template-based summaries, and keyword search fallback for Q&A.

## 🏃 Running the Application

### Local Setup
Launch the Streamlit dashboard:
```bash
streamlit run app/main.py
```

### 🐳 Docker Deployment (Recommended for OCR)
Since OCR requires system dependencies (`tesseract`), running via Docker is recommended.
```bash
docker-compose up --build
```
The app will be available at `http://localhost:8501`.

### ☁️ Streamlit Community Cloud
To deploy on Streamlit Community Cloud:
1. Push this repository to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io) and link your repo.
3. Add a `packages.txt` file in the root containing: `tesseract-ocr` and `poppler-utils`.
4. Set your API keys in the Advanced Settings (Secrets) section.

## 🧠 AI/ML Approach Used (MANDATORY)
The project employs a hybrid approach combining traditional heuristics and modern Machine Learning algorithms:
- **Named Entity Recognition (NER)**: We use the `spaCy` NLP library (`en_core_web_sm` model) to contextually identify generic entities such as `PERSON`, `ORG`, and custom terms. This is particularly useful for identifying business-sensitive data that doesn't follow a strict regex pattern.
- **Large Language Models (LLMs)**: We integrate with Gemini, OpenAI, and Groq via their official SDKs. The LLMs are utilized for two primary tasks:
  1. **Compliance Summarization**: Synthesizing the detected entities and risk classifications into actionable security and compliance reports (e.g., GDPR, DPDP Act).
  2. **Retrieval-Augmented Generation (RAG)**: For document Q&A, the document text is split and vectorized using `sentence-transformers` and stored in `ChromaDB`. The LLM then answers questions strictly grounded in the retrieved chunks.
- **Privacy-Preserving AI**: Crucially, all PII (Personally Identifiable Information) detected by Regex or NER is **masked** *before* being sent to any external LLM APIs, ensuring zero data leakage.

## 🚧 Challenges Faced (MANDATORY)
1. **Accurate PDF Extraction**: Handling varied PDF structures, including image-based (scanned) PDFs. This was mitigated by implementing an OCR fallback pipeline using `pytesseract` and `pdf2image`.
2. **LLM Hallucinations**: Preventing the AI from answering out-of-context questions in the Q&A section. We solved this by using strict system prompts and implementing a fallback rule if the context didn't contain the answer.
3. **API Reliability & Rate Limits**: Relying purely on external AI endpoints is brittle. We implemented a robust fallback mechanism that generates local template-based summaries if the LLM API is unavailable or rate-limited.
4. **Data Privacy**: Sending raw text to an LLM provider poses a massive security risk. We engineered a seamless masking layer that redacts all identified sensitive entities (e.g., replacing credit card numbers with `******`) before any text leaves the local machine.

## 🔮 Future Improvements (MANDATORY)
1. **Local LLM Integration**: Integrate with `Ollama` to run quantized LLMs completely offline, eliminating external API dependencies entirely.
2. **Advanced Redaction**: Support native PDF redaction, allowing the user to download a new PDF with blacked-out sections instead of just a masked `.txt` file.
3. **Enterprise Authentication**: Add OAuth2/SSO login and Role-Based Access Control (RBAC) so different users have different data access tiers.
4. **Additional Entity Models**: Train custom NER models using `Transformers` (e.g., BERT) specifically on domain-specific data like medical records (PHI) or legal documents for higher accuracy.

## 🧪 Testing

The project includes an extensive test suite (100+ tests). To run the tests:
```bash
pytest tests/ -v
```

## 🛡️ License

This project is intended for demonstration and evaluation purposes.
