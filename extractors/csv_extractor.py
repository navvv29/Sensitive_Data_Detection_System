"""
CSV Text Extractor
==================
Extracts text from CSV files by parsing into structured rows/columns,
and also concatenating cell content into scannable text for detection.

Handles:
- Standard CSV files with headers
- Various delimiters (auto-detected via csv.Sniffer)
- Files with encoding issues (chardet fallback)
- Empty CSVs and CSVs with no data rows
- Malformed/corrupted CSVs
"""

from typing import Optional
import io

import pandas as pd
import chardet

from extractors.pdf_extractor import ExtractionResult


def extract_text_from_csv(file_bytes: bytes, filename: str = "document.csv") -> ExtractionResult:
    """Extract text from a CSV file.
    
    Parses CSV into structured data (via pandas), then concatenates
    all cell values into a single text string for scanning. Preserves
    row/column structure in metadata for location tracking.
    
    Args:
        file_bytes: Raw bytes of the CSV file.
        filename: Original filename (for metadata).
        
    Returns:
        ExtractionResult with extracted text and structured row data.
    """
    result = ExtractionResult(file_type="csv")
    result.metadata["filename"] = filename
    result.metadata["file_size_bytes"] = len(file_bytes)
    
    if len(file_bytes) == 0:
        result.success = True
        result.text = ""
        result.total_lines = 0
        result.total_pages = 1
        result.pages = [{"page_num": 1, "text": "", "line_count": 0}]
        result.metadata["warning"] = "CSV file is empty"
        return result
    
    # Decode the CSV bytes
    text_content = _decode_csv_bytes(file_bytes, result)
    if text_content is None:
        result.success = False
        result.error = "Failed to decode CSV file with any supported encoding"
        return result
    
    # Parse with pandas
    try:
        df = pd.read_csv(io.StringIO(text_content), on_bad_lines="warn")
        
        result.metadata["rows"] = len(df)
        result.metadata["columns"] = len(df.columns)
        result.metadata["column_names"] = list(df.columns)
        
        # Build scannable text from all cells
        text_lines = []
        
        # Include header row
        header_line = " | ".join(str(col) for col in df.columns)
        text_lines.append(f"[Header] {header_line}")
        
        # Include each data row with row number for location tracking
        for row_idx, row in df.iterrows():
            row_values = []
            for col in df.columns:
                cell_value = str(row[col]) if pd.notna(row[col]) else ""
                row_values.append(cell_value)
            row_text = " | ".join(row_values)
            text_lines.append(f"[Row {row_idx + 1}] {row_text}")
        
        result.text = "\n".join(text_lines)
        result.total_lines = len(text_lines)
        result.total_pages = 1  # CSV treated as single page
        result.pages = [{
            "page_num": 1,
            "text": result.text,
            "line_count": result.total_lines,
        }]
        result.success = True
        
    except pd.errors.EmptyDataError:
        result.success = True
        result.text = ""
        result.total_lines = 0
        result.total_pages = 1
        result.pages = [{"page_num": 1, "text": "", "line_count": 0}]
        result.metadata["warning"] = "CSV file contains no data"
        
    except pd.errors.ParserError as e:
        result.success = False
        result.error = f"Failed to parse CSV: {str(e)}"
        
    except Exception as e:
        result.success = False
        result.error = f"Unexpected error processing CSV: {str(e)}"
    
    return result


def _decode_csv_bytes(file_bytes: bytes, result: ExtractionResult) -> Optional[str]:
    """Decode CSV file bytes with encoding detection.
    
    Same multi-strategy approach as TXT extractor.
    
    Args:
        file_bytes: Raw bytes to decode.
        result: ExtractionResult to update with encoding metadata.
        
    Returns:
        Decoded string, or None if all attempts fail.
    """
    # Strategy 1: UTF-8
    try:
        text = file_bytes.decode("utf-8")
        result.metadata["encoding"] = "utf-8"
        return text
    except (UnicodeDecodeError, ValueError):
        pass
    
    # Strategy 2: chardet
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
    
    # Strategy 3: Latin-1 fallback
    try:
        text = file_bytes.decode("latin-1")
        result.metadata["encoding"] = "latin-1"
        return text
    except Exception:
        pass
    
    return None
