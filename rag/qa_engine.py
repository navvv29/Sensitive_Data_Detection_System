"""
RAG Question-Answering Engine
===============================
Provides retrieval-augmented Q&A over uploaded documents.

Key design decisions:
- Counting-type questions (how many X) are answered from structured detection data
- Content questions use vector retrieval + LLM generation
- Answers never echo raw sensitive values back unmasked
- Uses ChromaDB for vector storage with sentence-transformers embeddings
"""

import os
import re
from typing import Optional

from rag.chunker import chunk_text, TextChunk
from detectors.unified_detector import DetectionResult
from classifiers.risk_classifier import RiskClassification
from summarizers.llm_client import LLMClient
from detectors.unified_detector import mask_detected_values


# Patterns for counting-type questions
COUNTING_PATTERNS = [
    (r"how many\s+(email|e-mail)s?", "email"),
    (r"how many\s+phone\s*(?:number)?s?", "phone"),
    (r"how many\s+aadhaar\s*(?:number)?s?", "aadhaar"),
    (r"how many\s+pan\s*(?:number)?s?", "pan"),
    (r"how many\s+credit\s*card\s*(?:number)?s?", "credit_card"),
    (r"how many\s+api\s*key?s?", "api_key"),
    (r"how many\s+password?s?", "password"),
    (r"how many\s+employee\s*id?s?", "employee_id"),
    (r"how many\s+(?:sensitive|entities|pii)", "_total"),
    (r"how many\s+ifsc", "ifsc"),
]

# Patterns for detection-summary questions
DETECTION_QUESTION_PATTERNS = [
    r"what\s+(?:sensitive|pii|personal)\s+data",
    r"what\s+(?:types?\s+of\s+)?(?:sensitive|private|confidential)\s+(?:data|info)",
    r"list\s+(?:all\s+)?(?:sensitive|detected|found)",
    r"what\s+(?:was|is)\s+(?:found|detected)",
]

# Patterns for risk/compliance questions
RISK_QUESTION_PATTERNS = [
    r"(?:what|which)\s+(?:compliance|regulatory)\s+risk",
    r"risk\s+(?:level|classification|assessment)",
    r"(?:what|which)\s+regulation",
    r"how\s+risky",
]

# Common external-knowledge prompts that should not be answered as document facts.
OFF_TOPIC_PATTERNS = [
    r"\bcapital\s+of\b",
    r"\bweather\b",
    r"\bstock\s+price\b",
    r"\bwho\s+won\b",
    r"\bpresident\s+of\b",
]


class QAEngine:
    """Question-Answering engine with RAG support.
    
    Handles three types of questions:
    1. Counting questions → answered from structured detection data
    2. Detection/risk questions → answered from detection results
    3. Content questions → answered via RAG (vector retrieval + LLM)
    """
    
    def __init__(
        self,
        document_text: str = "",
        detection_result: Optional[DetectionResult] = None,
        risk_classification: Optional[RiskClassification] = None,
        compliance_summary: str = "",
        llm_client: Optional[LLMClient] = None,
    ):
        """Initialize the QA engine with document context.
        
        Args:
            document_text: Full extracted document text.
            detection_result: Detection pipeline output.
            risk_classification: Risk classification output.
            compliance_summary: Generated compliance summary.
            llm_client: Optional LLM client for generative answers.
        """
        self.detection_result = detection_result
        self.risk_classification = risk_classification
        self.compliance_summary = compliance_summary
        self.llm_client = llm_client
        self.document_text = (
            mask_detected_values(document_text, detection_result.entities)
            if document_text and detection_result
            else document_text
        )
        
        # Chunk the document for RAG
        self.chunks = chunk_text(self.document_text) if self.document_text else []
        
        # Vector store (lazy-initialized)
        self._collection = None
        self._embeddings_ready = False
    
    def _ensure_embeddings(self):
        """Initialize ChromaDB and embed document chunks if not done."""
        if self._embeddings_ready or not self.chunks:
            return
        
        # Bypass ChromaDB for memory-constrained cloud environments (e.g., Render Free Tier)
        # This prevents loading a 200MB ONNX embedding model into RAM.
        # The engine will automatically fall back to _keyword_search which is highly efficient.
        return
    
    def answer(self, question: str) -> str:
        """Answer a natural-language question about the document.
        
        Routes to the appropriate answering strategy based on question type.
        
        Args:
            question: User's question in natural language.
            
        Returns:
            Answer string, grounded in document data.
        """
        question_lower = question.lower().strip()
        
        # Strategy 1: Counting questions → structured data
        counting_answer = self._try_counting_answer(question_lower)
        if counting_answer:
            return counting_answer
        
        # Strategy 2: Detection/risk summary questions
        summary_answer = self._try_summary_answer(question_lower)
        if summary_answer:
            return summary_answer

        if self._is_off_topic(question_lower):
            return (
                "I can only answer questions grounded in the uploaded document. "
                "Please ask about the document content, detected sensitive data, or compliance risks."
            )
        
        # Strategy 3: RAG-based content retrieval
        return self._rag_answer(question)

    def _is_off_topic(self, question: str) -> bool:
        """Detect common general-knowledge questions outside the document scope."""
        return any(re.search(pattern, question, re.IGNORECASE) for pattern in OFF_TOPIC_PATTERNS)
    
    def _try_counting_answer(self, question: str) -> Optional[str]:
        """Try to answer counting-type questions from structured data.
        
        Args:
            question: Lowercased question string.
            
        Returns:
            Answer string if this is a counting question, else None.
        """
        if not self.detection_result:
            return None
        
        for pattern, entity_type in COUNTING_PATTERNS:
            if re.search(pattern, question, re.IGNORECASE):
                if entity_type == "_total":
                    count = self.detection_result.total_entities
                    return (
                        f"A total of **{count} sensitive entities** were detected "
                        f"in the document across {len(self.detection_result.entity_counts)} "
                        f"different categories."
                    )
                else:
                    count = self.detection_result.entity_counts.get(entity_type, 0)
                    entity_label = entity_type.replace("_", " ").title()
                    if count == 0:
                        return f"No **{entity_label}** entities were detected in the document."
                    return (
                        f"**{count}** {entity_label} "
                        f"{'entity was' if count == 1 else 'entities were'} "
                        f"detected in the document."
                    )
        
        return None
    
    def _try_summary_answer(self, question: str) -> Optional[str]:
        """Try to answer detection/risk/compliance questions.
        
        Args:
            question: Lowercased question string.
            
        Returns:
            Formatted answer if applicable, else None.
        """
        # Detection summary questions
        for pattern in DETECTION_QUESTION_PATTERNS:
            if re.search(pattern, question, re.IGNORECASE):
                return self._format_detection_summary()
        
        # Risk/compliance questions
        for pattern in RISK_QUESTION_PATTERNS:
            if re.search(pattern, question, re.IGNORECASE):
                return self._format_risk_summary()
        
        # Document summary request
        if "summarize" in question or "summary" in question:
            if self.compliance_summary:
                return self.compliance_summary
            return self._format_detection_summary()
        
        return None
    
    def _format_detection_summary(self) -> str:
        """Format a summary of detected entities."""
        if not self.detection_result or self.detection_result.total_entities == 0:
            return "No sensitive data entities were detected in this document."
        
        lines = [
            f"**{self.detection_result.total_entities} sensitive entities** were detected:\n"
        ]
        
        for entity_type, count in sorted(
            self.detection_result.entity_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        ):
            label = entity_type.replace("_", " ").title()
            lines.append(f"- **{label}**: {count}")
        
        return "\n".join(lines)
    
    def _format_risk_summary(self) -> str:
        """Format a risk classification summary."""
        if not self.risk_classification:
            return "Risk classification has not been performed on this document."
        
        rc = self.risk_classification
        lines = [
            f"**Risk Level: {rc.risk_level}** (Score: {rc.risk_score:.0f})\n",
            rc.rationale,
        ]
        
        return "\n".join(lines)
    
    def _rag_answer(self, question: str) -> str:
        """Answer using RAG: retrieve relevant chunks + LLM generation.
        
        Args:
            question: User's question.
            
        Returns:
            Generated answer grounded in retrieved document chunks.
        """
        # Ensure embeddings are ready
        self._ensure_embeddings()
        
        # Retrieve relevant chunks
        retrieved_text = self._retrieve_chunks(question)
        
        if not retrieved_text:
            return (
                "I don't have enough context from the document to answer that question. "
                "Please try rephrasing or ask about the detected sensitive data."
            )
        
        # Generate answer with LLM if available
        if self.llm_client:
            return self._generate_rag_answer(question, retrieved_text)
        
        # Fallback: return retrieved chunks directly
        return (
            f"**Relevant document content:**\n\n{retrieved_text}\n\n"
            f"*Note: For AI-generated answers, configure an LLM API key.*"
        )
    
    def _retrieve_chunks(self, query: str, n_results: int = 3) -> str:
        """Retrieve the most relevant document chunks for a query.
        
        Args:
            query: Search query.
            n_results: Number of chunks to retrieve.
            
        Returns:
            Concatenated text of relevant chunks.
        """
        if self._collection is None or not self._embeddings_ready:
            # Fallback: simple keyword search
            return self._keyword_search(query)
        
        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=min(n_results, len(self.chunks)),
            )
            
            if results and results["documents"]:
                return "\n\n---\n\n".join(results["documents"][0])
        except Exception as e:
            print(f"Warning: ChromaDB query failed: {e}")
        
        return self._keyword_search(query)
    
    def _keyword_search(self, query: str, max_results: int = 3) -> str:
        """Simple keyword-based fallback search.
        
        Args:
            query: Search query.
            max_results: Maximum number of chunks to return.
            
        Returns:
            Concatenated relevant chunks.
        """
        if not self.chunks:
            return ""
        
        query_words = set(query.lower().split())
        scored_chunks = []
        
        for chunk in self.chunks:
            chunk_lower = chunk.text.lower()
            score = sum(1 for word in query_words if word in chunk_lower)
            if score > 0:
                scored_chunks.append((score, chunk))
        
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        top_chunks = [chunk.text for _, chunk in scored_chunks[:max_results]]
        
        return "\n\n---\n\n".join(top_chunks) if top_chunks else ""
    
    def _generate_rag_answer(self, question: str, context: str) -> str:
        """Generate an answer using LLM with retrieved context.
        
        Args:
            question: User's question.
            context: Retrieved document chunks.
            
        Returns:
            LLM-generated answer.
        """
        prompt = f"""Based on the following document content, answer the user's question.
Be concise and factual. If the answer cannot be found in the content, say so.
IMPORTANT: Do NOT reveal or echo any sensitive data values (PII, keys, passwords).
Use masked references only.

## Document Content:
{context}

## User Question:
{question}

## Answer:"""
        
        system_instruction = (
            "You are a document analysis assistant. Answer questions based on the "
            "provided document content. Never reveal sensitive values (PII, credentials, etc.)."
        )
        
        return self.llm_client.generate(
            prompt=prompt,
            system_instruction=system_instruction,
            temperature=0.2,
        )
