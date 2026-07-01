# Sensitive Data Detection & Compliance Assistant

An AI-powered document analysis tool designed to detect sensitive data, classify risk, and generate compliance guidance. Built with a decoupled architecture using **Next.js**, **FastAPI**, **spaCy**, **ChromaDB**, and **Groq LLM**.

## Architecture Overview 

The application follows a modern decoupled architecture:

- **Frontend (Next.js 15)**: A sleek, responsive user interface utilizing Tailwind CSS, React, and glassmorphism design. It manages file uploads, presents interactive dashboards (metrics, tables, summaries), and includes a conversational chat interface for Q&A.
- **Backend (FastAPI)**: A high-performance Python backend that orchestrates the AI and NLP pipelines. It exposes REST APIs for file uploads (`/api/upload`) and conversational chat (`/api/chat`).
- **Data Pipeline**: 
  - Text Extraction (PDF, TXT, CSV)
  - PII Detection (Regex + spaCy NLP)
  - Data Masking & Redaction
  - Risk Classification Algorithm
  - RAG Engine (ChromaDB Vector Store + Groq LLM) for summarization and answering questions about the redacted data without leaking PII to external servers.

## AI/ML approach used

The system employs a hybrid AI/ML approach to maximize accuracy and data privacy:

1. **Named Entity Recognition (NER)**: We use `spaCy` (a local NLP model) alongside highly optimized Regular Expressions to detect a wide range of standard PII (Emails, Phone Numbers, Aadhaar, PAN, Credit Cards, API Keys, etc.). This step occurs entirely locally.
2. **Data Redaction/Masking**: All detected sensitive entities are hard-masked (e.g., replaced with `[CONFIDENTIAL: EMAIL]`) before any data ever leaves the local machine.
3. **Retrieval-Augmented Generation (RAG)**: The masked document is chunked and embedded into a local **ChromaDB** vector database. 
4. **Large Language Models (LLMs)**: We integrate with **Groq** (via `llama-3.3-70b-versatile` or similar models) to perform high-speed, context-aware reasoning. The RAG engine retrieves relevant masked document chunks and passes them to the LLM to generate compliance summaries and answer user queries safely.

## Setup instructions 
### 1. Clone the Repository
```bash
git clone https://github.com/navvv29/Sensitive_Data_Detection_System.git
cd Sensitive_Data_Detection_System
```

### 2. Environment Variables
Create a `.env` file in the root directory:
```env
GROQ_API_KEY=your_groq_api_key_here
LLM_PROVIDER=groq
```

### 3. Running with Docker Compose
```bash
docker-compose up --build
```
This will start both the FastAPI backend (Port 8000) and the Next.js frontend (Port 3000). 
Access the UI at: `http://localhost:3000`

### 4. Running Locally (Manual)
**Backend:**
```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```
**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## Challenges faced 

- **Architecture Migration**: Transitioning from a tightly coupled Streamlit monolith to a decoupled Next.js + FastAPI architecture required careful management of stateless backend sessions to keep the RAG conversational memory intact across API requests.
- **Dependency Conflicts**: Handling exact Python dependency versions across different platforms (Windows/Linux) and managing `uvicorn` executable paths within virtual environments.
- **LLM Safety and Hallucinations**: Designing prompts and a fallback mechanism to ensure the LLM never regurgitates sensitive information, and accurately falls back to structured keyword search if an API key is missing.
- **Strict Parsing Limitations**: Tuning Regex boundaries and Luhn algorithms to ensure synthetic or anomalous edge cases (e.g., Aadhaar formats) were properly captured and validated.

## Future improvements 

- **Persistent Database**: Transition from in-memory session tracking (`SESSION_STORE`) to a persistent database like PostgreSQL or Redis for distributed, long-term session management.
- **Advanced OCR**: Integrate Tesseract or AWS Textract to support scanned PDFs and images, rather than relying solely on parseable text.
- **Local LLMs**: Incorporate support for local, open-weights models (via `Ollama`) to entirely eliminate the need for cloud-based LLM APIs, ensuring 100% air-gapped data compliance.
- **Role-Based Access Control (RBAC)**: Add user authentication and authorization so different compliance officers can have different access tiers to audit logs.


