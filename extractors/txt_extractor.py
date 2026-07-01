"""
TXT Text Extractor
==================
Extracts text from plain text files with automatic encoding detection.
Tries utf-8 first, falls back to chardet detection, then latin-1 as last resort.

Handles:
- UTF-8, Latin-1, and other encodings (via chardet)
- Empty files
- Very large files (with size warning)
- Binary files disguised as .txt (graceful failure)
"""

from typing import Optional

import chardet

from extractors.pdf_extractor import ExtractionResult


# Maximum file size before warning (10 MB)
MAX_FILE_SIZE_WARN = 10 * 1024 * 1024


def extract_text_from_txt(file_bytes: bytes, filename: str = "document.txt") -> ExtractionResult:
    """Extract text from a plain text file with encoding detection.
    
    Encoding priority:
    1. UTF-8 (most common)
    2. chardet auto-detection
    3. Latin-1 fallback (accepts all byte values)
    
    Args:
        file_bytes: Raw bytes of the text file.
        filename: Original filename (for metadata).
        
    Returns:
        ExtractionResult with extracted text and metadata.
    """
    result = ExtractionResult(file_type="txt")
    result.metadata["filename"] = filename
    result.metadata["file_size_bytes"] = len(file_bytes)
    
    # Size warning for very large files
    if len(file_bytes) > MAX_FILE_SIZE_WARN:
        result.metadata["warning"] = (
            f"Large file detected ({len(file_bytes) / (1024*1024):.1f} MB). "
            "Processing may take longer than usual."
        )
    
    if len(file_bytes) == 0:
        result.success = True
        result.text = ""
        result.total_lines = 0
        result.total_pages = 1
        result.pages = [{"page_num": 1, "text": "", "line_count": 0}]
        result.metadata["warning"] = "File is empty"
        return result
    
    # Try encoding detection
    text = _decode_bytes(file_bytes, result)
    
    if text is None:
        result.success = False
        result.error = "Failed to decode text file with any supported encoding"
        return result
    
    # Build result
    lines = text.split("\n")
    result.text = text
    result.total_lines = len(lines)
    result.total_pages = 1  # TXT files are treated as single-page
    result.pages = [{
        "page_num": 1,
        "text": text,
        "line_count": len(lines),
    }]
    result.success = True
    
    return result


def _decode_bytes(file_bytes: bytes, result: ExtractionResult) -> Optional[str]:
    """Attempt to decode bytes using multiple encoding strategies.
    
    Args:
        file_bytes: Raw bytes to decode.
        result: ExtractionResult to update with encoding metadata.
        
    Returns:
        Decoded string, or None if all attempts fail.
    """
    # Strategy 1: Try UTF-8
    try:
        text = file_bytes.decode("utf-8")
        result.metadata["encoding"] = "utf-8"
        return text
    except (UnicodeDecodeError, ValueError):
        pass
    
    # Strategy 2: chardet auto-detection
    try:
        detection = chardet.detect(file_bytes)
        detected_encoding = detection.get("encoding")
        confidence = detection.get("confidence", 0)
        
        if detected_encoding and confidence > 0.5:
            try:
                text = file_bytes.decode(detected_encoding)
                result.metadata["encoding"] = detected_encoding
                result.metadata["encoding_confidence"] = confidence
                return text
            except (UnicodeDecodeError, ValueError, LookupError):
                pass
    except Exception:
        pass
    
    # Strategy 3: Latin-1 fallback (never fails — maps all byte values)
    try:
        text = file_bytes.decode("latin-1")
        result.metadata["encoding"] = "latin-1"
        result.metadata["encoding_note"] = "Fallback encoding used; some characters may display incorrectly"
        return text
    except Exception:
        pass
    
    return None
