"""
Test suite for RAG and Question-Answering engine.
===================================================
Tests document chunking logic, QA routing, and fallback mechanisms.
LLM-dependent features (actual generative answers) are skipped or
mocked when run without an API key.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from rag.chunker import chunk_text, TextChunk
from rag.qa_engine import QAEngine
from detectors.unified_detector import DetectionResult
from classifiers.risk_classifier import RiskClassification


def _make_detection_result(entity_counts: dict) -> DetectionResult:
    result = DetectionResult()
    result.entity_counts = entity_counts
    result.total_entities = sum(entity_counts.values())
    return result


def _make_risk_classification(level: str, score: float) -> RiskClassification:
    rc = RiskClassification()
    rc.risk_level = level
    rc.risk_score = score
    rc.rationale = f"Risk is {level}"
    return rc


# =============================================================================
# Chunker Tests
# =============================================================================

class TestChunker:
    """Tests for the document chunking logic."""

    def test_empty_text(self):
        """Empty text should return empty chunks list."""
        assert chunk_text("") == []
        assert chunk_text("   \n   ") == []

    def test_single_small_chunk(self):
        """Text smaller than chunk size should return a single chunk."""
        text = "This is a small document."
        chunks = chunk_text(text, chunk_size=500, min_chunk_size=10)
        
        assert len(chunks) == 1
        assert chunks[0].text == text
        assert chunks[0].start_line == 1
        assert chunks[0].end_line == 1

    def test_multiple_chunks_with_overlap(self):
        """Long text should be split with overlap."""
        # Create 10 lines of text
        lines = [f"This is line number {i} of the document, with enough text to chunk." for i in range(10)]
        text = "\n".join(lines)
        
        # Very small chunk size to force splitting
        chunks = chunk_text(text, chunk_size=100, chunk_overlap=80, min_chunk_size=10)
        
        assert len(chunks) > 1
        
        # Check overlap
        first_chunk = chunks[0].text
        second_chunk = chunks[1].text
        
        # At least some part of the end of chunk 1 should be at the start of chunk 2
        last_line_of_first = first_chunk.split("\n")[-1]
        assert last_line_of_first in second_chunk

    def test_line_number_tracking(self):
        """Chunker should correctly track line numbers."""
        lines = [f"Line {i}" for i in range(1, 6)]
        text = "\n".join(lines)
        
        chunks = chunk_text(text, chunk_size=15, chunk_overlap=0, min_chunk_size=5)
        
        assert chunks[0].start_line == 1
        assert chunks[0].end_line >= 1


# =============================================================================
# QA Engine Tests
# =============================================================================

class TestQAEngine:
    """Tests for the QA Engine routing and response generation."""

    def test_counting_question_total(self):
        """Should correctly answer total entity count questions."""
        detection = _make_detection_result({"email": 2, "pan": 1})
        engine = QAEngine(detection_result=detection)
        
        answer = engine.answer("How many sensitive entities were found?")
        assert "3" in answer
        assert "sensitive entities" in answer.lower()

    def test_counting_question_specific(self):
        """Should correctly answer specific entity count questions."""
        detection = _make_detection_result({"email": 5})
        engine = QAEngine(detection_result=detection)
        
        answer = engine.answer("How many emails are there?")
        assert "5" in answer
        assert "email" in answer.lower()

    def test_counting_question_zero(self):
        """Should gracefully handle counts of 0."""
        detection = _make_detection_result({"email": 5})
        engine = QAEngine(detection_result=detection)
        
        answer = engine.answer("How many PAN numbers are there?")
        assert "no" in answer.lower()
        assert "pan" in answer.lower()

    def test_detection_summary_question(self):
        """Should provide detection summary when asked."""
        detection = _make_detection_result({"email": 2, "pan": 1})
        engine = QAEngine(detection_result=detection)
        
        answer = engine.answer("What sensitive data was found?")
        assert "Email" in answer
        assert "Pan" in answer
        assert "3 sensitive entities" in answer.lower()

    def test_risk_summary_question(self):
        """Should provide risk classification when asked."""
        rc = _make_risk_classification("HIGH", 45.0)
        engine = QAEngine(risk_classification=rc)
        
        answer = engine.answer("What is the risk level?")
        assert "HIGH" in answer
        assert "45" in answer

    def test_keyword_fallback_search(self):
        """Should fallback to keyword search when ChromaDB/embeddings fail or are absent."""
        doc_text = "The quick brown fox jumps over the lazy dog. Secret project X is launching tomorrow."
        engine = QAEngine(document_text=doc_text)
        
        # Question that triggers RAG strategy
        answer = engine.answer("What is launching tomorrow?")
        
        # Without an LLM client, it should return the retrieved context directly
        assert "Secret project X" in answer
        assert "AI-generated answers" in answer
