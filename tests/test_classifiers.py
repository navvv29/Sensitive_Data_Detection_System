"""
Test suite for the risk classification engine.
================================================
Tests weighted scoring, threshold mapping, and rationale generation
with three designed test cases (Low, Medium, High risk).
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from detectors.regex_detector import DetectedEntity
from detectors.unified_detector import DetectionResult
from classifiers.risk_classifier import (
    classify_risk, RiskClassification,
    ENTITY_WEIGHTS, RISK_THRESHOLDS, _score_to_level,
)


def _make_detection_result(entity_counts: dict) -> DetectionResult:
    """Helper to create a DetectionResult with given entity counts."""
    result = DetectionResult()
    result.entity_counts = entity_counts
    result.total_entities = sum(entity_counts.values())
    return result


# =============================================================================
# Scoring Logic Tests
# =============================================================================

class TestScoringLogic:
    """Tests for the weighted scoring mechanism."""

    def test_empty_document_scores_zero(self):
        """Document with no entities should score 0."""
        result = _make_detection_result({})
        classification = classify_risk(result)
        assert classification.risk_score == 0.0
        assert classification.risk_level == "LOW"

    def test_score_calculation(self):
        """Verify score = weight × count for each entity type."""
        result = _make_detection_result({"email": 3, "pan": 1})
        classification = classify_risk(result)
        
        expected_score = (2 * 3) + (10 * 1)  # email=2×3 + pan=10×1 = 16
        assert classification.risk_score == expected_score
        
    def test_score_breakdown_present(self):
        """Verify score breakdown shows per-type contribution."""
        result = _make_detection_result({"email": 2, "aadhaar": 1})
        classification = classify_risk(result)
        
        assert "email" in classification.score_breakdown
        assert "aadhaar" in classification.score_breakdown
        assert classification.score_breakdown["email"]["contribution"] == 4  # 2×2
        assert classification.score_breakdown["aadhaar"]["contribution"] == 10  # 10×1

    def test_unknown_entity_type_gets_default_weight(self):
        """Unknown entity types should get default weight of 1."""
        result = _make_detection_result({"unknown_type": 5})
        classification = classify_risk(result)
        assert classification.risk_score == 5  # 1×5


# =============================================================================
# Threshold Tests
# =============================================================================

class TestThresholds:
    """Tests for score-to-level threshold mapping."""

    def test_low_threshold(self):
        """Score < 10 should be LOW."""
        assert _score_to_level(0) == "LOW"
        assert _score_to_level(5) == "LOW"
        assert _score_to_level(9.9) == "LOW"

    def test_medium_threshold(self):
        """10 <= score < 30 should be MEDIUM."""
        assert _score_to_level(10) == "MEDIUM"
        assert _score_to_level(20) == "MEDIUM"
        assert _score_to_level(29.9) == "MEDIUM"

    def test_high_threshold(self):
        """Score >= 30 should be HIGH."""
        assert _score_to_level(30) == "HIGH"
        assert _score_to_level(100) == "HIGH"
        assert _score_to_level(1000) == "HIGH"


# =============================================================================
# Classification Scenario Tests
# =============================================================================

class TestClassificationScenarios:
    """Test with 3 designed documents: Low, Medium, High risk."""

    def test_low_risk_document(self):
        """Document with only emails → LOW risk.
        
        Scenario: A public contact list with 3 email addresses.
        Score: 3 × 2 = 6 (below LOW threshold of 10).
        """
        result = _make_detection_result({"email": 3})
        classification = classify_risk(result)
        
        assert classification.risk_level == "LOW"
        assert classification.risk_score == 6
        assert "LOW" in classification.rationale

    def test_medium_risk_document(self):
        """Document with phones + employee IDs → MEDIUM risk.
        
        Scenario: Internal employee directory.
        Score: 3×4 + 2×4 + 1×2 = 12+8+2 = 22 (MEDIUM range: 10-30).
        """
        result = _make_detection_result({
            "phone": 3,
            "employee_id": 2,
            "email": 1,
        })
        classification = classify_risk(result)
        
        assert classification.risk_level == "MEDIUM"
        assert 10 <= classification.risk_score < 30
        assert "MEDIUM" in classification.rationale

    def test_high_risk_document(self):
        """Document with critical PII → HIGH risk.
        
        Scenario: HR record with Aadhaar, PAN, credit card, API keys.
        Score: 10+10+10+9+2 = 41 (well above HIGH threshold of 30).
        """
        result = _make_detection_result({
            "aadhaar": 1,
            "pan": 1,
            "credit_card": 1,
            "api_key": 1,
            "email": 1,
        })
        classification = classify_risk(result)
        
        assert classification.risk_level == "HIGH"
        assert classification.risk_score >= 30
        assert "HIGH" in classification.rationale


# =============================================================================
# Rationale & Top Factors Tests
# =============================================================================

class TestRationale:
    """Tests for classification rationale and top risk factors."""

    def test_rationale_present(self):
        """Classification must include human-readable rationale."""
        result = _make_detection_result({"pan": 1})
        classification = classify_risk(result)
        
        assert len(classification.rationale) > 0
        assert "Risk Level" in classification.rationale

    def test_top_risk_factors_sorted(self):
        """Top risk factors should be sorted by contribution (highest first)."""
        result = _make_detection_result({
            "email": 5,      # contribution: 10
            "aadhaar": 1,    # contribution: 10
            "phone": 1,      # contribution: 4
        })
        classification = classify_risk(result)
        
        contributions = [f["contribution"] for f in classification.top_risk_factors]
        assert contributions == sorted(contributions, reverse=True)

    def test_empty_document_rationale(self):
        """Empty document should have specific safe rationale."""
        result = _make_detection_result({})
        classification = classify_risk(result)
        
        assert "No sensitive data" in classification.rationale
        assert "LOW" in classification.rationale

    def test_serialization(self):
        """RiskClassification should serialize to dict."""
        result = _make_detection_result({"pan": 1})
        classification = classify_risk(result)
        
        d = classification.to_dict()
        assert "risk_level" in d
        assert "risk_score" in d
        assert "score_breakdown" in d
        assert "rationale" in d
        assert "top_risk_factors" in d


# =============================================================================
# Weight Documentation Tests
# =============================================================================

class TestWeightDocumentation:
    """Tests that verify the weight system is properly defined."""

    def test_all_common_types_have_weights(self):
        """All common entity types must have defined weights."""
        required_types = [
            "aadhaar", "pan", "email", "phone", "credit_card",
            "ifsc", "api_key", "password", "employee_id",
            "confidential_marker", "person_name", "organization",
            "business_sensitive",
        ]
        for entity_type in required_types:
            assert entity_type in ENTITY_WEIGHTS, f"Missing weight for {entity_type}"

    def test_critical_types_have_highest_weights(self):
        """Critical PII types must have the highest weights."""
        critical_types = ["aadhaar", "pan", "credit_card"]
        for t in critical_types:
            assert ENTITY_WEIGHTS[t] >= 10

    def test_low_types_have_lowest_weights(self):
        """Low-risk types must have low weights."""
        low_types = ["email", "person_name", "organization"]
        for t in low_types:
            assert ENTITY_WEIGHTS[t] <= 3

    def test_thresholds_are_contiguous(self):
        """Risk thresholds must cover the full range without gaps."""
        thresholds = list(RISK_THRESHOLDS.values())
        # LOW starts at 0
        assert thresholds[0][0] == 0
        # Each threshold's end matches the next's start
        for i in range(len(thresholds) - 1):
            assert thresholds[i][1] == thresholds[i + 1][0]
