"""
Test suite for AI-generated compliance summary.
=================================================
Tests the compliance summary generator including template fallback,
prompt construction, regulation mapping, and output structure.

Note: LLM-based tests require an API key and are marked with
@pytest.mark.skipif for environments without keys configured.
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from detectors.unified_detector import DetectionResult
from classifiers.risk_classifier import RiskClassification, classify_risk
from summarizers.compliance_summary import (
    generate_compliance_summary,
    _build_grounding_context,
    _build_prompt,
    _generate_template_summary,
    REGULATION_MAP,
)
from summarizers.llm_client import LLMClient


def _make_detection_result(entity_counts: dict) -> DetectionResult:
    """Helper to create a DetectionResult with given entity counts."""
    result = DetectionResult()
    result.entity_counts = entity_counts
    result.total_entities = sum(entity_counts.values())
    return result


# =============================================================================
# Regulation Mapping Tests
# =============================================================================

class TestRegulationMapping:
    """Tests for entity-to-regulation mapping."""

    def test_aadhaar_maps_to_dpdp(self):
        """Aadhaar should map to DPDP Act."""
        assert any("DPDP" in r for r in REGULATION_MAP["aadhaar"])

    def test_credit_card_maps_to_pci_dss(self):
        """Credit card should map to PCI-DSS."""
        assert any("PCI" in r for r in REGULATION_MAP["credit_card"])

    def test_api_key_maps_to_security_standards(self):
        """API keys should map to SOC 2 / ISO 27001."""
        regs = REGULATION_MAP["api_key"]
        assert any("SOC" in r for r in regs) or any("ISO" in r for r in regs)

    def test_all_entity_types_have_mapping(self):
        """All known entity types should have at least one regulation."""
        for entity_type, regulations in REGULATION_MAP.items():
            assert len(regulations) > 0, f"No regulations for {entity_type}"


# =============================================================================
# Grounding Context Tests
# =============================================================================

class TestGroundingContext:
    """Tests for the context builder that grounds LLM prompts."""

    def test_context_includes_risk_level(self):
        """Context should include risk level."""
        detection = _make_detection_result({"email": 2})
        classification = classify_risk(detection)
        context = _build_grounding_context(detection, classification)
        
        assert "risk_level" in context
        assert context["risk_level"] in ("LOW", "MEDIUM", "HIGH")

    def test_context_includes_entity_summary(self):
        """Context should summarize detected entities."""
        detection = _make_detection_result({"pan": 1, "email": 3})
        classification = classify_risk(detection)
        context = _build_grounding_context(detection, classification)
        
        assert "entity_summary" in context
        assert "Pan" in context["entity_summary"]
        assert "Email" in context["entity_summary"]

    def test_context_identifies_regulations(self):
        """Context should list applicable regulations."""
        detection = _make_detection_result({"credit_card": 1})
        classification = classify_risk(detection)
        context = _build_grounding_context(detection, classification)
        
        assert "applicable_regulations" in context
        assert len(context["applicable_regulations"]) > 0

    def test_context_for_empty_detection(self):
        """Context should handle empty detection gracefully."""
        detection = _make_detection_result({})
        classification = classify_risk(detection)
        context = _build_grounding_context(detection, classification)
        
        assert context["total_entities"] == 0
        assert context["risk_level"] == "LOW"


# =============================================================================
# Prompt Construction Tests
# =============================================================================

class TestPromptConstruction:
    """Tests for the LLM prompt builder."""

    def test_prompt_includes_detection_data(self):
        """Prompt should contain actual detection data."""
        detection = _make_detection_result({"aadhaar": 1, "email": 2})
        classification = classify_risk(detection)
        context = _build_grounding_context(detection, classification)
        prompt = _build_prompt(context)
        
        assert "Aadhaar" in prompt
        assert "Email" in prompt
        assert str(context["total_entities"]) in prompt

    def test_prompt_requests_three_sections(self):
        """Prompt should request all three summary sections."""
        detection = _make_detection_result({"pan": 1})
        classification = classify_risk(detection)
        context = _build_grounding_context(detection, classification)
        prompt = _build_prompt(context)
        
        assert "Compliance Observations" in prompt
        assert "Security Risks" in prompt
        assert "Remediation" in prompt

    def test_prompt_warns_against_raw_values(self):
        """Prompt should instruct LLM not to echo raw values."""
        detection = _make_detection_result({"pan": 1})
        classification = classify_risk(detection)
        context = _build_grounding_context(detection, classification)
        prompt = _build_prompt(context)
        
        assert "Do NOT mention" in prompt or "raw sensitive values" in prompt.lower()


# =============================================================================
# Template Summary Tests
# =============================================================================

class TestTemplateSummary:
    """Tests for the template-based fallback summary."""

    def test_template_has_three_sections(self):
        """Template summary must include all three required sections."""
        detection = _make_detection_result({"aadhaar": 1, "email": 2})
        classification = classify_risk(detection)
        context = _build_grounding_context(detection, classification)
        summary = _generate_template_summary(context, detection, classification)
        
        assert "Compliance Observations" in summary
        assert "Security Risks" in summary
        assert "Remediation" in summary

    def test_template_high_risk_remediation(self):
        """HIGH risk should produce strong remediation steps."""
        detection = _make_detection_result({
            "aadhaar": 2, "pan": 1, "credit_card": 1, "api_key": 1
        })
        classification = classify_risk(detection)
        context = _build_grounding_context(detection, classification)
        summary = _generate_template_summary(context, detection, classification)
        
        assert "Restrict" in summary or "Restrict access" in summary.lower()
        assert "Redact" in summary or "Rotate" in summary

    def test_template_low_risk_remediation(self):
        """LOW risk should produce standard handling steps."""
        detection = _make_detection_result({"email": 1})
        classification = classify_risk(detection)
        context = _build_grounding_context(detection, classification)
        summary = _generate_template_summary(context, detection, classification)
        
        assert "Standard" in summary or "standard" in summary

    def test_template_includes_regulations(self):
        """Template should mention applicable regulations."""
        detection = _make_detection_result({"credit_card": 1})
        classification = classify_risk(detection)
        context = _build_grounding_context(detection, classification)
        summary = _generate_template_summary(context, detection, classification)
        
        assert "PCI-DSS" in summary

    def test_template_no_raw_values(self):
        """Template summary must not contain any raw sensitive values."""
        detection = _make_detection_result({"aadhaar": 1, "pan": 1})
        classification = classify_risk(detection)
        context = _build_grounding_context(detection, classification)
        summary = _generate_template_summary(context, detection, classification)
        
        # Should not contain any specific PII values
        # (we only pass counts, not values, so this is inherently safe)
        assert "2345" not in summary
        assert "ABCPK" not in summary


# =============================================================================
# Integration: generate_compliance_summary (without LLM)
# =============================================================================

class TestGenerateComplianceSummary:
    """Tests for the main summary generation function."""

    def test_generates_without_llm_client(self):
        """Should fallback to template when no LLM client provided."""
        detection = _make_detection_result({"pan": 1, "email": 2})
        classification = classify_risk(detection)
        
        summary = generate_compliance_summary(detection, classification, llm_client=None)
        
        assert len(summary) > 100
        assert "Compliance" in summary

    def test_generates_for_empty_document(self):
        """Should handle documents with no entities."""
        detection = _make_detection_result({})
        classification = classify_risk(detection)
        
        summary = generate_compliance_summary(detection, classification, llm_client=None)
        
        assert len(summary) > 0

    def test_output_is_string(self):
        """Summary must always be a string."""
        detection = _make_detection_result({"email": 1})
        classification = classify_risk(detection)
        
        summary = generate_compliance_summary(detection, classification, llm_client=None)
        
        assert isinstance(summary, str)
