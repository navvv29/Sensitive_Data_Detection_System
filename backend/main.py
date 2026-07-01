"""
FastAPI Backend for Sensitive Data Detection System
=================================================
Exposes endpoints for file extraction, detection, classification, summarization, and Q&A.
"""

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid
import sys
import os
import uvicorn
from typing import List, Optional

# Add the parent directory to sys.path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from extractors.pdf_extractor import extract_text_from_pdf, ExtractionResult
from extractors.txt_extractor import extract_text_from_txt
from extractors.csv_extractor import extract_text_from_csv
from detectors.unified_detector import run_unified_detection, mask_detected_values
from classifiers.risk_classifier import classify_risk
from summarizers.llm_client import LLMClient
from summarizers.compliance_summary import generate_compliance_summary
from rag.qa_engine import QAEngine
from utils.audit_logger import log_document_processing

app = FastAPI(title="Sensitive Data Detection API", version="1.0")

# Enable CORS for Next.js frontend and cloud deployments
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store for RAG engines (keyed by session_id)
# In production, use a proper session store (e.g., Redis).
SESSION_STORE = {}

class ChatRequest(BaseModel):
    session_id: str
    message: str

def get_file_extension(filename: str) -> str:
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower()

def extract_document(file_bytes: bytes, filename: str, file_type: str) -> ExtractionResult:
    extractors = {
        "pdf": extract_text_from_pdf,
        "txt": extract_text_from_txt,
        "csv": extract_text_from_csv,
    }
    extractor = extractors.get(file_type)
    if not extractor:
        return ExtractionResult(success=False, error=f"Unsupported file type: {file_type}")
    return extractor(file_bytes, filename)

@app.post("/api/upload")
async def upload_documents(
    files: List[UploadFile] = File(...),
    enable_nlp: bool = Form(True),
    use_llm: bool = Form(True),
    llm_provider: str = Form("groq")
):
    try:
        combined_text = ""
        total_lines = 0
        filenames = []
        
        for file in files:
            file_bytes = await file.read()
            filename = file.filename
            file_type = get_file_extension(filename)
            filenames.append(filename)
            
            result = extract_document(file_bytes, filename, file_type)
            if not result.success:
                raise HTTPException(status_code=400, detail=f"Extraction failed for {filename}: {result.error}")
                
            combined_text += f"\n\n--- Document: {filename} ---\n\n" + result.text
            total_lines += result.total_lines
            
        # Run Detection
        detection = run_unified_detection(combined_text, enable_nlp=enable_nlp)
        
        # Run Classification
        classification = classify_risk(detection)
        
        # Summarize
        os.environ["LLM_PROVIDER"] = llm_provider
        llm_client = None
        if use_llm:
            try:
                llm_client = LLMClient()
                if not llm_client.is_available():
                    llm_client = None
            except Exception:
                llm_client = None
                
        summary = generate_compliance_summary(detection, classification, llm_client)
        
        # Initialize QA Engine
        qa_engine = QAEngine(
            document_text=mask_detected_values(combined_text, detection.entities),
            detection_result=detection,
            risk_classification=classification,
            compliance_summary=summary,
            llm_client=llm_client,
        )
        
        session_id = str(uuid.uuid4())
        SESSION_STORE[session_id] = {
            "qa_engine": qa_engine,
            "masked_text": qa_engine.document_text,
            "filenames": filenames
        }
        
        # Audit Log
        log_document_processing(
            filename=", ".join(filenames),
            file_type="multiple",
            total_entities=detection.total_entities,
            risk_level=classification.risk_level,
            risk_score=classification.risk_score
        )
        
        # Prepare response
        entities_list = [
            {
                "type": e.entity_type,
                "masked_value": e.masked_value,
                "confidence": e.confidence,
                "method": e.method,
                "line": e.location.get("line")
            } for e in detection.entities
        ]
        
        return {
            "session_id": session_id,
            "total_entities": detection.total_entities,
            "entities": entities_list,
            "risk_level": classification.risk_level,
            "risk_score": classification.risk_score,
            "risk_factors": classification.top_risk_factors,
            "summary": summary,
            "masked_text": qa_engine.document_text
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
async def chat_with_document(request: ChatRequest):
    session_data = SESSION_STORE.get(request.session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found or expired.")
        
    qa_engine = session_data["qa_engine"]
    response = qa_engine.answer(request.message)
    return {"reply": response}

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
