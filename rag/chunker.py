"""
Document Chunker
==================
Splits document text into chunks suitable for embedding and vector storage.
Uses a sliding window approach with configurable chunk size and overlap.
"""

from dataclasses import dataclass, field


@dataclass
class TextChunk:
    """A single chunk of document text.
    
    Attributes:
        text: The chunk content.
        chunk_id: Sequential chunk identifier.
        start_line: Starting line number in original document.
        end_line: Ending line number in original document.
        metadata: Additional metadata (source file, page, etc.)
    """
    text: str
    chunk_id: int = 0
    start_line: int = 0
    end_line: int = 0
    metadata: dict = field(default_factory=dict)


def chunk_text(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    min_chunk_size: int = 50,
) -> list[TextChunk]:
    """Split text into overlapping chunks for embedding.
    
    Uses a character-based sliding window with line-boundary alignment
    to avoid splitting mid-sentence where possible.
    
    Args:
        text: Full document text.
        chunk_size: Target characters per chunk.
        chunk_overlap: Overlap between consecutive chunks.
        min_chunk_size: Minimum chunk size (skip smaller fragments).
        
    Returns:
        List of TextChunk objects.
    """
    if not text or not text.strip():
        return []
    
    lines = text.split("\n")
    chunks = []
    current_chunk_lines = []
    current_char_count = 0
    chunk_start_line = 1
    chunk_id = 0
    
    for line_idx, line in enumerate(lines):
        line_len = len(line) + 1  # +1 for newline
        
        if current_char_count + line_len > chunk_size and current_chunk_lines:
            # Emit current chunk
            chunk_text_content = "\n".join(current_chunk_lines)
            if len(chunk_text_content.strip()) >= min_chunk_size:
                chunks.append(TextChunk(
                    text=chunk_text_content,
                    chunk_id=chunk_id,
                    start_line=chunk_start_line,
                    end_line=chunk_start_line + len(current_chunk_lines) - 1,
                ))
                chunk_id += 1
            
            # Calculate overlap: keep last N characters worth of lines
            overlap_lines = []
            overlap_chars = 0
            for prev_line in reversed(current_chunk_lines):
                if overlap_chars + len(prev_line) > chunk_overlap:
                    break
                overlap_lines.insert(0, prev_line)
                overlap_chars += len(prev_line) + 1
            
            current_chunk_lines = overlap_lines
            current_char_count = overlap_chars
            chunk_start_line = line_idx + 1 - len(overlap_lines)
        
        current_chunk_lines.append(line)
        current_char_count += line_len
    
    # Emit final chunk
    if current_chunk_lines:
        chunk_text_content = "\n".join(current_chunk_lines)
        if len(chunk_text_content.strip()) >= min_chunk_size:
            chunks.append(TextChunk(
                text=chunk_text_content,
                chunk_id=chunk_id,
                start_line=chunk_start_line,
                end_line=chunk_start_line + len(current_chunk_lines) - 1,
            ))
    
    return chunks
