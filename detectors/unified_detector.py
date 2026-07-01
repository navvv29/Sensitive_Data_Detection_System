"""
Unified Sensitive Data Detection Pipeline
==========================================
Combines regex-based and NLP-based detectors into a single pipeline.
Returns structured detection results with deduplication and unified output format.
"""

from dataclasses import dataclass, field
from typing import Optional

from detectors.regex_detector import DetectedEntity, run_all_regex_detectors
from detectors.nlp_detector import run_all_nlp_detectors


@dataclass
class DetectionResult:
    """Aggregated result from the unified detection pipeline.
    
    Attributes:
        entities: List of all detected entities.
        entity_counts: Count of entities per type.
        total_entities: Total number of entities found.
        detection_methods: Set of methods used (regex, nlp).
        metadata: Additional detection metadata.
    """
    entities: list[DetectedEntity] = field(default_factory=list)
    entity_counts: dict = field(default_factory=dict)
    total_entities: int = 0
    detection_methods: set = field(default_factory=set)
    metadata: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "total_entities": self.total_entities,
            "entity_counts": self.entity_counts,
            "detection_methods": list(self.detection_methods),
            "entities": [
                {
                    "entity_type": e.entity_type,
                    "masked_value": e.masked_value,
                    "location": e.location,
                    "method": e.method,
                    "confidence": e.confidence,
                }
                for e in self.entities
            ],
            "metadata": self.metadata,
        }


def run_unified_detection(text: str, enable_nlp: bool = True) -> DetectionResult:
    """Run the full detection pipeline (regex + NLP) on text.
    
    Executes all regex detectors first (fast, high-precision), then
    NLP detectors (slower, contextual). Deduplicates overlapping
    detections and aggregates counts.
    
    Args:
        text: Full document text to analyze.
        enable_nlp: Whether to run NLP detectors (can be disabled for speed).
        
    Returns:
        DetectionResult with all detected entities and statistics.
    """
    result = DetectionResult()
    
    if not text or not text.strip():
        result.metadata["note"] = "Empty or blank document — no entities to detect"
        return result
    
    # Phase 1: Regex-based detection (fast, structured patterns)
    regex_entities = run_all_regex_detectors(text)
    result.detection_methods.add("regex")
    
    # Phase 2: NLP-based detection (contextual, unstructured)
    nlp_entities = []
    if enable_nlp:
        try:
            nlp_entities = run_all_nlp_detectors(text)
            result.detection_methods.add("nlp")
        except Exception as e:
            result.metadata["nlp_error"] = str(e)
    
    # Combine and deduplicate
    all_entities = regex_entities + nlp_entities
    deduped_entities = _deduplicate_entities(all_entities)
    
    # Sort by location (line number, then position)
    deduped_entities.sort(key=lambda e: (
        e.location.get("line", 0),
        e.location.get("start", 0),
    ))
    
    # Aggregate counts
    entity_counts = {}
    for entity in deduped_entities:
        entity_type = entity.entity_type
        entity_counts[entity_type] = entity_counts.get(entity_type, 0) + 1
    
    result.entities = deduped_entities
    result.entity_counts = entity_counts
    result.total_entities = len(deduped_entities)
    result.metadata["regex_count"] = len(regex_entities)
    result.metadata["nlp_count"] = len(nlp_entities)
    result.metadata["deduped_count"] = len(all_entities) - len(deduped_entities)
    
    return result


def mask_detected_values(text: str, entities: list[DetectedEntity]) -> str:
    """Return document text with detected raw values replaced by masked values."""
    if not text or not entities:
        return text

    masked_text = text
    for entity in sorted(entities, key=lambda e: len(e.value), reverse=True):
        if entity.value:
            masked_text = masked_text.replace(entity.value, entity.masked_value)
    return masked_text


def _deduplicate_entities(entities: list[DetectedEntity]) -> list[DetectedEntity]:
    """Remove duplicate detections based on overlapping positions.
    
    When regex and NLP detect the same text span, prefer the detection
    with higher confidence. If equal, prefer regex (more precise for
    structured patterns).
    
    Args:
        entities: List of potentially overlapping entities.
        
    Returns:
        Deduplicated list of entities.
    """
    if not entities:
        return []
    
    # Group by line number
    by_line: dict[int, list[DetectedEntity]] = {}
    no_line: list[DetectedEntity] = []
    
    for entity in entities:
        line = entity.location.get("line")
        if line is not None:
            if line not in by_line:
                by_line[line] = []
            by_line[line].append(entity)
        else:
            no_line.append(entity)
    
    result = list(no_line)
    
    for line_num, line_entities in by_line.items():
        # Sort by start position, then by confidence (descending)
        line_entities.sort(key=lambda e: (
            e.location.get("start", 0),
            -e.confidence,
        ))
        
        kept = []
        for entity in line_entities:
            start = entity.location.get("start", 0)
            end = entity.location.get("end", 0)
            
            # Check if this entity overlaps with any already kept
            is_duplicate = False
            for kept_entity in kept:
                k_start = kept_entity.location.get("start", 0)
                k_end = kept_entity.location.get("end", 0)
                
                # Check overlap
                if start < k_end and end > k_start:
                    # Overlapping — keep the one with higher confidence
                    if entity.confidence > kept_entity.confidence:
                        kept.remove(kept_entity)
                        kept.append(entity)
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                kept.append(entity)
        
        result.extend(kept)
    
    return result
