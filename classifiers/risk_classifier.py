"""
Risk Classification Engine
============================
Classifies documents into Low/Medium/High risk based on detected sensitive entities.

Uses an explicit, documented weighted scoring system:
- Each entity type has a predefined weight reflecting its sensitivity
- Total score = sum(weight × count) for each entity type
- Score mapped to risk level via configurable thresholds

This approach is fully transparent and auditable — the classification
rationale (which entities drove the score) is returned alongside the label.

Scoring Weights (Justification):
- Critical PII (Aadhaar, PAN, credit card): Weight 10 — direct identity theft risk,
  regulated under DPDP Act 2023, PCI-DSS
- Financial data (bank/IFSC, business_sensitive): Weight 8 — financial fraud risk
- Secrets (API keys, passwords): Weight 9 — system compromise risk
- Moderate PII (phone, employee_id): Weight 4 — moderate identity risk
- Low PII (email, person_name, organization): Weight 2 — publicly findable info
- Context markers (confidential_marker): Weight 3 — indicates document sensitivity

Threshold Mapping:
- Low Risk:    score < 10 — no or minimal sensitive data
- Medium Risk: 10 <= score < 30 — moderate sensitive data present
- High Risk:   score >= 30 — critical identifiers present
"""

from dataclasses import dataclass, field
from typing import Optional

from detectors.unified_detector import DetectionResult


# Entity type weights — higher weight = more sensitive
ENTITY_WEIGHTS: dict[str, int] = {
    # Critical PII — direct identity theft / regulatory violation
    "aadhaar": 10,
    "pan": 10,
    "credit_card": 10,
    
    # Secrets — system/infrastructure compromise
    "api_key": 9,
    "password": 9,
    "secret": 9,
    
    # Financial — fraud and financial loss risk
    "ifsc": 8,
    "bank_account": 8,
    "business_sensitive": 8,
    
    # Moderate PII — identity correlation risk
    "phone": 4,
    "employee_id": 4,
    
    # Context markers — document classification sensitivity
    "confidential_marker": 3,
    
    # Low PII — publicly available or low-risk
    "email": 2,
    "person_name": 2,
    "organization": 1,
}

# Risk level thresholds
RISK_THRESHOLDS = {
    "LOW": (0, 10),        # score < 10
    "MEDIUM": (10, 30),    # 10 <= score < 30
    "HIGH": (30, float("inf")),  # score >= 30
}


@dataclass
class RiskClassification:
    """Result of risk classification for a document.
    
    Attributes:
        risk_level: Classification label (LOW, MEDIUM, HIGH).
        risk_score: Numerical risk score.
        score_breakdown: Per-entity-type contribution to the score.
        rationale: Human-readable explanation of the classification.
        top_risk_factors: The entity types contributing most to the score.
        thresholds: The threshold ranges used for classification.
        entity_counts: Count of each entity type found.
    """
    risk_level: str = "LOW"
    risk_score: float = 0.0
    score_breakdown: dict = field(default_factory=dict)
    rationale: str = ""
    top_risk_factors: list = field(default_factory=list)
    thresholds: dict = field(default_factory=dict)
    entity_counts: dict = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "risk_level": self.risk_level,
            "risk_score": self.risk_score,
            "score_breakdown": self.score_breakdown,
            "rationale": self.rationale,
            "top_risk_factors": self.top_risk_factors,
            "thresholds": {k: list(v) for k, v in self.thresholds.items()},
            "entity_counts": self.entity_counts,
        }


def classify_risk(detection_result: DetectionResult) -> RiskClassification:
    """Classify a document's risk level based on detection results.
    
    Applies the weighted scoring formula:
        total_score = Σ (weight_i × count_i) for each entity type i
    
    Then maps the score to a risk level using defined thresholds.
    
    Args:
        detection_result: Output from the unified detection pipeline.
        
    Returns:
        RiskClassification with level, score, breakdown, and rationale.
    """
    classification = RiskClassification()
    classification.thresholds = dict(RISK_THRESHOLDS)
    classification.entity_counts = dict(detection_result.entity_counts)
    
    # Calculate weighted score per entity type
    total_score = 0.0
    score_breakdown = {}
    
    for entity_type, count in detection_result.entity_counts.items():
        weight = ENTITY_WEIGHTS.get(entity_type, 1)  # Default weight 1 for unknown types
        contribution = weight * count
        score_breakdown[entity_type] = {
            "count": count,
            "weight": weight,
            "contribution": contribution,
        }
        total_score += contribution
    
    classification.risk_score = total_score
    classification.score_breakdown = score_breakdown
    
    # Determine risk level from thresholds
    classification.risk_level = _score_to_level(total_score)
    
    # Identify top risk factors (sorted by contribution, descending)
    sorted_factors = sorted(
        score_breakdown.items(),
        key=lambda x: x[1]["contribution"],
        reverse=True,
    )
    classification.top_risk_factors = [
        {"entity_type": entity_type, **details}
        for entity_type, details in sorted_factors[:5]  # Top 5
    ]
    
    # Generate human-readable rationale
    classification.rationale = _generate_rationale(
        classification.risk_level,
        total_score,
        classification.top_risk_factors,
        detection_result.total_entities,
    )
    
    return classification


def _score_to_level(score: float) -> str:
    """Map a numerical risk score to a risk level label.
    
    Args:
        score: Total weighted risk score.
        
    Returns:
        Risk level string: 'LOW', 'MEDIUM', or 'HIGH'.
    """
    for level, (low, high) in RISK_THRESHOLDS.items():
        if low <= score < high:
            return level
    return "HIGH"  # Fallback


def _generate_rationale(
    level: str,
    score: float,
    top_factors: list,
    total_entities: int,
) -> str:
    """Generate a human-readable rationale for the classification.
    
    Args:
        level: Risk level label.
        score: Total risk score.
        top_factors: Top contributing entity types.
        total_entities: Total number of entities detected.
        
    Returns:
        Multi-line rationale string.
    """
    if total_entities == 0:
        return (
            "Risk Level: LOW\n"
            "No sensitive data entities were detected in this document. "
            "The document appears to be safe for general handling."
        )
    
    lines = [
        f"Risk Level: {level} (Score: {score:.0f})",
        f"Total sensitive entities detected: {total_entities}",
        "",
        "Top risk factors:",
    ]
    
    for factor in top_factors:
        entity_type = factor["entity_type"].replace("_", " ").title()
        lines.append(
            f"  • {entity_type}: {factor['count']} found "
            f"(weight={factor['weight']}, contribution={factor['contribution']})"
        )
    
    lines.append("")
    
    if level == "HIGH":
        lines.append(
            "⚠️ HIGH RISK: This document contains critical sensitive data "
            "that could lead to identity theft, financial fraud, or system "
            "compromise if exposed. Immediate action recommended."
        )
    elif level == "MEDIUM":
        lines.append(
            "⚡ MEDIUM RISK: This document contains moderate sensitive data. "
            "Access should be restricted and the document should be handled "
            "according to your organization's data protection policies."
        )
    else:
        lines.append(
            "✅ LOW RISK: This document contains minimal or no sensitive data. "
            "Standard handling procedures are sufficient."
        )
    
    return "\n".join(lines)
