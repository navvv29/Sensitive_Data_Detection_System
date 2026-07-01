"""
NLP-Based Sensitive Data Detector
==================================
Uses spaCy Named Entity Recognition (NER) for detecting unstructured/contextual
sensitive entities that regex alone cannot reliably catch.

Detects:
- Person names (PERSON entities)
- Organization names (ORG entities) 
- Confidential/sensitive context keywords and phrases
- Business-sensitive information markers

Uses en_core_web_sm model by default (configurable via env var).
"""

import os
import re
from typing import Optional

import spacy

from detectors.regex_detector import DetectedEntity, mask_value


# Lazy-loaded spaCy model (loaded once on first use)
_nlp_model = None


def _get_nlp_model():
    """Lazy-load the spaCy NLP model.
    
    Uses SPACY_MODEL env var if set, defaults to en_core_web_sm.
    Caches the model after first load for performance.
    
    Returns:
        Loaded spaCy Language model.
    """
    global _nlp_model
    if _nlp_model is None:
        model_name = os.environ.get("SPACY_MODEL", "en_core_web_sm")
        try:
            _nlp_model = spacy.load(model_name)
        except OSError:
            raise RuntimeError(
                f"spaCy model '{model_name}' not found. "
                f"Install it with: python -m spacy download {model_name}"
            )
    return _nlp_model


# Confidential/sensitive context keywords and phrases
CONFIDENTIAL_KEYWORDS = [
    "confidential",
    "internal use only",
    "trade secret",
    "proprietary",
    "classified",
    "restricted",
    "sensitive",
    "do not share",
    "do not distribute",
    "private and confidential",
    "strictly confidential",
    "nda",
    "non-disclosure",
    "privileged",
    "secret",
]

# Business-sensitive phrase patterns
BUSINESS_SENSITIVE_PATTERNS = [
    r"(?:revenue|profit|loss|salary|compensation|ctc|bonus)\s*(?:of|is|was|:)\s*(?:INR|USD|\$|₹)?\s*[\d,\.]+",
    r"(?:launch|release)\s+(?:date|plan|scheduled)\s*(?:for|on|:)",
    r"(?:merger|acquisition|takeover)\s+(?:of|with|plan)",
    r"(?:market\s+(?:share|capture|strategy))",
    r"(?:strategic\s+(?:plan|initiative|partnership))",
]


def detect_ner_entities(text: str) -> list[DetectedEntity]:
    """Detect named entities using spaCy NER.
    
    Identifies PERSON and ORG entities that may represent sensitive
    PII when found in the context of confidential documents.
    
    Args:
        text: Full document text to analyze.
        
    Returns:
        List of DetectedEntity objects for NER-detected entities.
    """
    nlp = _get_nlp_model()
    entities = []
    
    # Process text in chunks if very long (spaCy has max length limits)
    max_length = nlp.max_length
    text_chunks = _chunk_text(text, max_length)
    
    line_offset = 0
    for chunk in text_chunks:
        doc = nlp(chunk)
        chunk_lines = chunk.split("\n")
        
        for ent in doc.ents:
            if ent.label_ in ("PERSON", "ORG"):
                ent_text = ent.text.strip()
                
                # Heuristic 1: Skip very short entities
                if len(ent_text) < 3:
                    continue
                    
                # Heuristic 2: Contextual and format filtering for PERSON
                if ent.label_ == "PERSON":
                    # Skip if it contains numbers
                    if any(char.isdigit() for char in ent_text):
                        continue
                    
                    # Skip known common location false positives
                    blacklist = {"india", "bangalore", "bengaluru", "mumbai", "delhi", "chennai", "hyderabad", "pune", "kerala"}
                    if ent_text.lower() in blacklist:
                        continue
                        
                    # Skip if preceded by a location-based preposition
                    if ent.start > 0:
                        prev_token = doc[ent.start - 1].text.lower()
                        if prev_token in ("in", "at", "from", "to", "near", "visit", "located"):
                            continue
                            
                # Heuristic 3: Format filtering for ORG
                if ent.label_ == "ORG":
                    # Must have some alphabetical characters
                    if not any(char.isalpha() for char in ent_text):
                        continue

                # Calculate line number within the chunk
                text_before_entity = chunk[:ent.start_char]
                line_in_chunk = text_before_entity.count("\n") + 1
                line_num = line_offset + line_in_chunk
                
                entity_type = "person_name" if ent.label_ == "PERSON" else "organization"
                
                entities.append(DetectedEntity(
                    entity_type=entity_type,
                    value=ent_text,
                    masked_value=mask_value(ent_text, entity_type),
                    location={"line": line_num, "start": ent.start_char, "end": ent.end_char},
                    method="nlp",
                    confidence=0.70,  # NER confidence is generally moderate
                    pattern_name=f"spacy_{ent.label_}",
                ))
        
        line_offset += len(chunk_lines)
    
    return entities


def detect_confidential_keywords(text: str) -> list[DetectedEntity]:
    """Detect confidential/sensitive context markers in text.
    
    Scans for keywords and phrases that indicate the document
    contains confidential or sensitive information.
    
    Args:
        text: Full document text to scan.
        
    Returns:
        List of DetectedEntity objects for keyword matches.
    """
    entities = []
    text_lower = text.lower()
    
    for line_num, line in enumerate(text.split("\n"), start=1):
        line_lower = line.lower()
        
        for keyword in CONFIDENTIAL_KEYWORDS:
            # Find all occurrences of the keyword in this line
            start = 0
            while True:
                idx = line_lower.find(keyword, start)
                if idx == -1:
                    break
                
                # Get the actual matched text (preserving case)
                matched_text = line[idx:idx + len(keyword)]
                
                entities.append(DetectedEntity(
                    entity_type="confidential_marker",
                    value=matched_text,
                    masked_value=f"[CONFIDENTIAL: {keyword.upper()}]",
                    location={"line": line_num, "start": idx, "end": idx + len(keyword)},
                    method="nlp",
                    confidence=0.85,
                    pattern_name="confidential_keyword",
                ))
                
                start = idx + len(keyword)
    
    return entities


def detect_business_sensitive(text: str) -> list[DetectedEntity]:
    """Detect business-sensitive information patterns.
    
    Uses regex patterns to find financial figures, strategic plans,
    and other business-sensitive content tied to internal operations.
    
    Args:
        text: Full document text to scan.
        
    Returns:
        List of DetectedEntity objects for business-sensitive matches.
    """
    entities = []
    
    for line_num, line in enumerate(text.split("\n"), start=1):
        for pattern in BUSINESS_SENSITIVE_PATTERNS:
            for match in re.finditer(pattern, line, re.IGNORECASE):
                value = match.group(0)
                entities.append(DetectedEntity(
                    entity_type="business_sensitive",
                    value=value,
                    masked_value="[BUSINESS SENSITIVE CONTENT]",
                    location={"line": line_num, "start": match.start(), "end": match.end()},
                    method="nlp",
                    confidence=0.75,
                    pattern_name="business_sensitive_pattern",
                ))
    
    return entities


def run_all_nlp_detectors(text: str) -> list[DetectedEntity]:
    """Run all NLP-based detectors on the given text.
    
    Args:
        text: Full document text to analyze.
        
    Returns:
        Combined list of all NLP-detected entities.
    """
    all_entities = []
    
    detectors = [
        detect_ner_entities,
        detect_confidential_keywords,
        detect_business_sensitive,
    ]
    
    for detector in detectors:
        try:
            entities = detector(text)
            all_entities.extend(entities)
        except Exception as e:
            print(f"Warning: NLP detector {detector.__name__} failed: {e}")
    
    return all_entities


def _chunk_text(text: str, max_length: int) -> list[str]:
    """Split text into chunks that fit within spaCy's max_length.
    
    Splits on paragraph boundaries to preserve context.
    
    Args:
        text: Full text to chunk.
        max_length: Maximum character length per chunk.
        
    Returns:
        List of text chunks.
    """
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    paragraphs = text.split("\n\n")
    current_chunk = ""
    
    for para in paragraphs:
        if len(current_chunk) + len(para) + 2 > max_length:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = para
        else:
            current_chunk = current_chunk + "\n\n" + para if current_chunk else para
    
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks
