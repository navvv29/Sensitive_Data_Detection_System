"""
PDF Text Extractor
==================
Extracts text from PDF files using pdfplumber with page-level tracking.
Returns structured extraction results with page numbers and line counts.

Handles:
- Standard text PDFs
- Multi-page documents
- Empty pages (skipped gracefully)
- Corrupted/unreadable PDFs (returns error without crashing)
"""

from dataclasses import dataclass, field
from typing import Optional
import io

import pdfplumber


@dataclass
class ExtractionResult:
    """Structured result from document text extraction.
    
    Attributes:
        success: Whether extraction completed successfully.
        text: Full extracted text content.
        pages: List of per-page extraction data (page_num, text, line_count).
        total_pages: Total number of pages in the document.
        total_lines: Total line count across all pages.
        file_type: Source file type (pdf/txt/csv).
        error: Error message if extraction failed.
        metadata: Additional extraction metadata.
    """
    success: bool = True
    text: str = ""
    pages: list = field(default_factory=list)
    total_pages: int = 0
    total_lines: int = 0
    file_type: str = ""
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)


def extract_text_from_pdf(file_bytes: bytes, filename: str = "document.pdf") -> ExtractionResult:
    """Extract text from a PDF file.
    
    Uses pdfplumber for text extraction with page-level tracking.
    Each page's text is stored separately with page number and line count.
    
    Args:
        file_bytes: Raw bytes of the PDF file.
        filename: Original filename (for metadata).
        
    Returns:
        ExtractionResult with extracted text, page data, and metadata.
    """
    result = ExtractionResult(file_type="pdf")
    result.metadata["filename"] = filename
    
    try:
        pdf_stream = io.BytesIO(file_bytes)
        
        with pdfplumber.open(pdf_stream) as pdf:
            result.total_pages = len(pdf.pages)
            
            if result.total_pages == 0:
                result.success = True
                result.text = ""
                result.metadata["warning"] = "PDF has no pages"
                return result
            
            all_text_parts = []
            
            for page_num, page in enumerate(pdf.pages, start=1):
                try:
                    page_text = page.extract_text() or ""
                    page_lines = page_text.split("\n") if page_text.strip() else []
                    line_count = len(page_lines)
                    
                    page_data = {
                        "page_num": page_num,
                        "text": page_text,
                        "line_count": line_count,
                    }
                    result.pages.append(page_data)
                    
                    if page_text.strip():
                        all_text_parts.append(page_text)
                    
                    result.total_lines += line_count
                    
                except Exception as page_err:
                    # Handle individual page extraction errors gracefully
                    page_data = {
                        "page_num": page_num,
                        "text": "",
                        "line_count": 0,
                        "error": str(page_err),
                    }
                    result.pages.append(page_data)
            
            result.text = "\n\n".join(all_text_parts)
            
            # Check if any text was extracted
            if not result.text.strip():
                try:
                    import pytesseract
                    from pdf2image import convert_from_bytes
                    
                    images = convert_from_bytes(file_bytes)
                    ocr_text_parts = []
                    
                    for page_num, image in enumerate(images, start=1):
                        page_text = pytesseract.image_to_string(image)
                        
                        if page_text.strip():
                            ocr_text_parts.append(page_text)
                            
                        # Update the corresponding page data
                        if page_num - 1 < len(result.pages):
                            result.pages[page_num - 1]["text"] = page_text
                            result.pages[page_num - 1]["line_count"] = len(page_text.split("\n"))
                            result.pages[page_num - 1]["metadata"] = {"ocr_used": True}
                        else:
                            result.pages.append({
                                "page_num": page_num,
                                "text": page_text,
                                "line_count": len(page_text.split("\n")),
                                "metadata": {"ocr_used": True}
                            })
                    
                    result.text = "\n\n".join(ocr_text_parts)
                    result.total_lines = sum(p.get("line_count", 0) for p in result.pages)
                    
                    if result.text.strip():
                        result.metadata["warning"] = "Scanned PDF detected. Text extracted using OCR."
                    else:
                        result.metadata["warning"] = "No text could be extracted from PDF, even with OCR."
                        
                except Exception as ocr_err:
                    result.metadata["warning"] = (
                        f"No text could be extracted. OCR fallback failed: {str(ocr_err)}. "
                        "Ensure Tesseract and Poppler are installed on the system."
                    )
            
            result.success = True
            
    except Exception as e:
        result.success = False
        result.error = f"Failed to extract text from PDF: {str(e)}"
    
    return result
