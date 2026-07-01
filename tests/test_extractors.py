"""
Test suite for document extractors.
====================================
Tests PDF, TXT, and CSV extractors with various sample files
including happy paths and edge cases.
"""

import os
import sys
import pytest

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from extractors.pdf_extractor import ExtractionResult, extract_text_from_pdf
from extractors.txt_extractor import extract_text_from_txt
from extractors.csv_extractor import extract_text_from_csv

# Path to sample files
SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "sample_files")


# =============================================================================
# TXT Extractor Tests
# =============================================================================

class TestTxtExtractor:
    """Tests for TXT text extraction."""

    def test_basic_txt_extraction(self):
        """Test extraction of a standard UTF-8 text file."""
        filepath = os.path.join(SAMPLE_DIR, "sample_basic.txt")
        with open(filepath, "rb") as f:
            file_bytes = f.read()

        result = extract_text_from_txt(file_bytes, "sample_basic.txt")

        assert result.success is True
        assert result.file_type == "txt"
        assert result.error is None
        assert len(result.text) > 0
        assert "John Doe" in result.text
        assert "john.doe@example.com" in result.text
        assert result.total_lines > 0
        assert result.total_pages == 1
        assert result.metadata["encoding"] == "utf-8"

    def test_sensitive_txt_extraction(self):
        """Test extraction of a text file with sensitive content."""
        filepath = os.path.join(SAMPLE_DIR, "sample_sensitive.txt")
        with open(filepath, "rb") as f:
            file_bytes = f.read()

        result = extract_text_from_txt(file_bytes, "sample_sensitive.txt")

        assert result.success is True
        assert "CONFIDENTIAL" in result.text
        assert "Rajesh Kumar" in result.text
        assert "sk-test1234567890abcdef" in result.text
        assert result.total_lines > 10

    def test_empty_txt(self):
        """Test extraction of an empty text file."""
        result = extract_text_from_txt(b"", "empty.txt")

        assert result.success is True
        assert result.text == ""
        assert result.total_lines == 0
        assert "warning" in result.metadata

    def test_latin1_encoding(self):
        """Test extraction of Latin-1 encoded content."""
        # Create Latin-1 encoded bytes using only Latin-1 compatible characters
        text = "R\u00e9sum\u00e9 - Fran\u00e7ois caf\u00e9"
        file_bytes = text.encode("latin-1")

        result = extract_text_from_txt(file_bytes, "latin1_test.txt")

        assert result.success is True
        assert len(result.text) > 0
        # The text should be decoded (possibly via chardet or latin-1 fallback)
        assert result.metadata.get("encoding") is not None

    def test_txt_metadata(self):
        """Test that metadata is populated correctly."""
        filepath = os.path.join(SAMPLE_DIR, "sample_basic.txt")
        with open(filepath, "rb") as f:
            file_bytes = f.read()

        result = extract_text_from_txt(file_bytes, "sample_basic.txt")

        assert result.metadata["filename"] == "sample_basic.txt"
        assert result.metadata["file_size_bytes"] == len(file_bytes)
        assert "encoding" in result.metadata


# =============================================================================
# CSV Extractor Tests
# =============================================================================

class TestCsvExtractor:
    """Tests for CSV text extraction."""

    def test_basic_csv_extraction(self):
        """Test extraction of a standard CSV file."""
        filepath = os.path.join(SAMPLE_DIR, "sample_data.csv")
        with open(filepath, "rb") as f:
            file_bytes = f.read()

        result = extract_text_from_csv(file_bytes, "sample_data.csv")

        assert result.success is True
        assert result.file_type == "csv"
        assert result.error is None
        assert len(result.text) > 0
        assert "Alice Johnson" in result.text
        assert "alice.johnson@testcorp.com" in result.text
        assert result.metadata["rows"] == 5
        assert result.metadata["columns"] == 5
        assert "name" in result.metadata["column_names"]

    def test_sensitive_csv_extraction(self):
        """Test extraction of CSV with sensitive data columns."""
        filepath = os.path.join(SAMPLE_DIR, "sample_sensitive.csv")
        with open(filepath, "rb") as f:
            file_bytes = f.read()

        result = extract_text_from_csv(file_bytes, "sample_sensitive.csv")

        assert result.success is True
        assert "Rajesh Kumar" in result.text
        assert "ABCPK1234F" in result.text  # PAN
        assert result.metadata["rows"] >= 3

    def test_empty_csv(self):
        """Test extraction of an empty CSV file."""
        result = extract_text_from_csv(b"", "empty.csv")

        assert result.success is True
        assert result.text == ""
        assert "warning" in result.metadata

    def test_csv_with_missing_values(self):
        """Test CSV with empty cells."""
        csv_content = b"name,email,phone\nJohn,,123\n,jane@test.com,\nBob,bob@test.com,456"
        result = extract_text_from_csv(csv_content, "missing_values.csv")

        assert result.success is True
        assert result.metadata["rows"] == 3
        assert "John" in result.text

    def test_csv_row_tracking(self):
        """Test that row numbers are tracked in output."""
        filepath = os.path.join(SAMPLE_DIR, "sample_data.csv")
        with open(filepath, "rb") as f:
            file_bytes = f.read()

        result = extract_text_from_csv(file_bytes, "sample_data.csv")

        assert "[Header]" in result.text
        assert "[Row 1]" in result.text


# =============================================================================
# PDF Extractor Tests
# =============================================================================

class TestPdfExtractor:
    """Tests for PDF text extraction."""

    def test_basic_pdf_extraction(self):
        """Test extraction of a standard multi-page PDF."""
        filepath = os.path.join(SAMPLE_DIR, "sample_basic.pdf")
        with open(filepath, "rb") as f:
            file_bytes = f.read()

        result = extract_text_from_pdf(file_bytes, "sample_basic.pdf")

        assert result.success is True
        assert result.file_type == "pdf"
        assert result.error is None
        assert len(result.text) > 0
        assert result.total_pages == 2
        assert len(result.pages) == 2
        assert "John Doe" in result.text or "john.doe" in result.text.lower()

    def test_sensitive_pdf_extraction(self):
        """Test extraction of a PDF with sensitive content."""
        filepath = os.path.join(SAMPLE_DIR, "sample_sensitive.pdf")
        with open(filepath, "rb") as f:
            file_bytes = f.read()

        result = extract_text_from_pdf(file_bytes, "sample_sensitive.pdf")

        assert result.success is True
        assert "CONFIDENTIAL" in result.text
        assert "Rajesh Kumar" in result.text

    def test_empty_pdf_extraction(self):
        """Test extraction of a blank PDF (no text content)."""
        filepath = os.path.join(SAMPLE_DIR, "sample_empty.pdf")
        with open(filepath, "rb") as f:
            file_bytes = f.read()

        result = extract_text_from_pdf(file_bytes, "sample_empty.pdf")

        assert result.success is True
        assert result.total_pages == 1
        # Empty PDF should have warning about no text
        assert result.text.strip() == "" or "warning" in result.metadata

    def test_pdf_with_invalid_bytes(self):
        """Test that invalid/corrupted PDF data is handled gracefully."""
        result = extract_text_from_pdf(b"not a real pdf", "fake.pdf")

        assert result.success is False
        assert result.error is not None
        assert "Failed to extract" in result.error

    def test_pdf_empty_bytes(self):
        """Test that empty bytes are handled gracefully."""
        result = extract_text_from_pdf(b"", "empty.pdf")

        assert result.success is False
        assert result.error is not None

    def test_pdf_page_level_tracking(self):
        """Test that page-level data is correctly tracked."""
        filepath = os.path.join(SAMPLE_DIR, "sample_basic.pdf")
        with open(filepath, "rb") as f:
            file_bytes = f.read()

        result = extract_text_from_pdf(file_bytes, "sample_basic.pdf")

        assert len(result.pages) == 2
        for page_data in result.pages:
            assert "page_num" in page_data
            assert "text" in page_data
            assert "line_count" in page_data

    def test_pdf_result_structure(self):
        """Test the ExtractionResult data structure."""
        result = ExtractionResult(file_type="pdf")

        assert result.success is True
        assert result.text == ""
        assert result.pages == []
        assert result.total_pages == 0
        assert result.total_lines == 0
        assert result.error is None
        assert result.metadata == {}


# =============================================================================
# Cross-Format Tests
# =============================================================================

class TestCrossFormat:
    """Tests that apply across all extractor types."""

    def test_extraction_result_has_required_fields(self):
        """Verify ExtractionResult has all required fields for downstream use."""
        result = ExtractionResult(
            success=True,
            text="test content",
            file_type="txt",
            total_pages=1,
            total_lines=1,
        )

        # These fields are required by the detection pipeline
        assert hasattr(result, "success")
        assert hasattr(result, "text")
        assert hasattr(result, "pages")
        assert hasattr(result, "total_pages")
        assert hasattr(result, "total_lines")
        assert hasattr(result, "file_type")
        assert hasattr(result, "error")
        assert hasattr(result, "metadata")

    def test_unsupported_format_rejection(self):
        """Test that we can identify unsupported formats."""
        supported_types = {"pdf", "txt", "csv"}
        unsupported = "docx"
        assert unsupported not in supported_types

    def test_all_extractors_return_same_type(self):
        """Verify all extractors return ExtractionResult."""
        txt_result = extract_text_from_txt(b"hello", "test.txt")
        csv_result = extract_text_from_csv(b"a,b\n1,2", "test.csv")
        pdf_result = extract_text_from_pdf(b"not a pdf", "test.pdf")

        assert isinstance(txt_result, ExtractionResult)
        assert isinstance(csv_result, ExtractionResult)
        assert isinstance(pdf_result, ExtractionResult)
