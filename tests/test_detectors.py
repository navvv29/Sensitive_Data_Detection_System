"""
Test suite for sensitive data detectors.
==========================================
Tests regex-based, NLP-based, and unified detection pipeline
using synthetic test data (no real PII).
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from detectors.regex_detector import (
    detect_aadhaar, detect_pan, detect_email, detect_phone,
    detect_credit_card, detect_bank_details, detect_api_keys_passwords,
    detect_employee_ids, run_all_regex_detectors, mask_value, _luhn_check,
)
from detectors.nlp_detector import (
    detect_ner_entities, detect_confidential_keywords,
    detect_business_sensitive, run_all_nlp_detectors,
)
from detectors.unified_detector import run_unified_detection


# =============================================================================
# Masking Tests
# =============================================================================

class TestMasking:
    """Tests for value masking logic."""

    def test_mask_aadhaar(self):
        """Aadhaar should show only last 4 digits."""
        masked = mask_value("2345 6789 0123", "aadhaar")
        assert "0123" in masked
        assert "2345" not in masked

    def test_mask_email(self):
        """Email should show only first char of local part and full domain."""
        masked = mask_value("john.doe@example.com", "email")
        assert "@example.com" in masked
        assert "john.doe" not in masked

    def test_mask_pan(self):
        """PAN should show first 3 and last 1 character."""
        masked = mask_value("ABCPK1234F", "pan")
        assert masked.startswith("ABC")
        assert masked.endswith("F")
        assert "PK1234" not in masked

    def test_mask_api_key(self):
        """API keys should show only first 4 chars."""
        masked = mask_value("sk-test1234567890abcdef", "api_key")
        assert masked.startswith("sk-t")
        assert "1234567890" not in masked

    def test_mask_credit_card(self):
        """Credit card should show only last 4 digits."""
        masked = mask_value("4111111111111111", "credit_card")
        assert "1111" in masked
        assert "4111111111" not in masked

    def test_mask_phone(self):
        """Phone should show only last 4 digits."""
        masked = mask_value("+91 98765 43210", "phone")
        assert "3210" in masked


# =============================================================================
# Aadhaar Detection Tests
# =============================================================================

class TestAadhaarDetection:
    """Tests for Aadhaar number detection."""

    def test_detect_spaced_aadhaar(self):
        """Detect Aadhaar in XXXX XXXX XXXX format."""
        text = "Aadhaar: 2345 6789 0123"
        entities = detect_aadhaar(text)
        assert len(entities) >= 1
        assert entities[0].entity_type == "aadhaar"

    def test_detect_hyphenated_aadhaar(self):
        """Detect Aadhaar with hyphens."""
        text = "ID: 2345-6789-0123"
        entities = detect_aadhaar(text)
        assert len(entities) >= 1

    def test_detect_continuous_aadhaar(self):
        """Detect Aadhaar without separators."""
        text = "Number: 234567890123"
        entities = detect_aadhaar(text)
        assert len(entities) >= 1

    def test_no_false_positive_short_number(self):
        """Reject numbers shorter than 12 digits."""
        text = "Phone: 98765 43210"
        entities = detect_aadhaar(text)
        # Phone numbers (10 digits) should not be detected as Aadhaar
        for e in entities:
            digits = ''.join(c for c in e.value if c.isdigit())
            assert len(digits) == 12

    def test_aadhaar_masking(self):
        """Detected Aadhaar values must be masked."""
        text = "Aadhaar: 2345 6789 0123"
        entities = detect_aadhaar(text)
        for entity in entities:
            assert "2345" not in entity.masked_value


# =============================================================================
# PAN Detection Tests
# =============================================================================

class TestPanDetection:
    """Tests for PAN number detection."""

    def test_detect_valid_pan(self):
        """Detect valid PAN format."""
        text = "PAN: ABCPK1234F"
        entities = detect_pan(text)
        assert len(entities) == 1
        assert entities[0].entity_type == "pan"

    def test_reject_lowercase_pan(self):
        """PAN must be uppercase."""
        text = "Not PAN: abcpk1234f"
        entities = detect_pan(text)
        assert len(entities) == 0

    def test_pan_masking(self):
        """Detected PAN values must be masked."""
        text = "PAN: ABCPK1234F"
        entities = detect_pan(text)
        assert len(entities) == 1
        assert "PK1234" not in entities[0].masked_value


# =============================================================================
# Email Detection Tests
# =============================================================================

class TestEmailDetection:
    """Tests for email address detection."""

    def test_detect_standard_email(self):
        """Detect standard email format."""
        text = "Contact: john.doe@example.com"
        entities = detect_email(text)
        assert len(entities) == 1
        assert entities[0].entity_type == "email"

    def test_detect_multiple_emails(self):
        """Detect multiple emails in text."""
        text = "Emails: alice@test.com and bob@company.org"
        entities = detect_email(text)
        assert len(entities) == 2

    def test_email_masking(self):
        """Email should be masked with only domain visible."""
        text = "Email: john.doe@example.com"
        entities = detect_email(text)
        assert len(entities) == 1
        assert "@example.com" in entities[0].masked_value
        assert "john.doe" not in entities[0].masked_value


# =============================================================================
# Phone Detection Tests
# =============================================================================

class TestPhoneDetection:
    """Tests for phone number detection."""

    def test_detect_indian_mobile_with_prefix(self):
        """Detect Indian mobile with +91."""
        text = "Phone: +91 98765 43210"
        entities = detect_phone(text)
        assert len(entities) >= 1

    def test_detect_indian_mobile_without_prefix(self):
        """Detect 10-digit Indian mobile."""
        text = "Call: 9876543210"
        entities = detect_phone(text)
        assert len(entities) >= 1

    def test_phone_masking(self):
        """Phone numbers should be masked."""
        text = "Phone: +91 98765 43210"
        entities = detect_phone(text)
        for entity in entities:
            assert "98765" not in entity.masked_value


# =============================================================================
# Credit Card Detection Tests
# =============================================================================

class TestCreditCardDetection:
    """Tests for credit card number detection."""

    def test_detect_visa_card(self):
        """Detect Visa card number (starts with 4)."""
        text = "Card: 4111 1111 1111 1111"
        entities = detect_credit_card(text)
        assert len(entities) >= 1
        assert entities[0].entity_type == "credit_card"

    def test_luhn_validation(self):
        """Verify Luhn algorithm works correctly."""
        assert _luhn_check("4111111111111111") is True  # Valid Visa test number
        assert _luhn_check("4111111111111112") is False  # Invalid

    def test_credit_card_masking(self):
        """Credit card should show only last 4 digits."""
        text = "Card: 4111111111111111"
        entities = detect_credit_card(text)
        for entity in entities:
            assert "41111111" not in entity.masked_value


# =============================================================================
# Bank/IFSC Detection Tests
# =============================================================================

class TestBankDetection:
    """Tests for bank details detection."""

    def test_detect_ifsc_code(self):
        """Detect standard IFSC code."""
        text = "IFSC: SBIN0001234"
        entities = detect_bank_details(text)
        assert len(entities) >= 1
        assert entities[0].entity_type == "ifsc"

    def test_ifsc_masking(self):
        """IFSC should show only bank code (first 4 chars)."""
        text = "IFSC: SBIN0001234"
        entities = detect_bank_details(text)
        for entity in entities:
            assert entity.masked_value.startswith("SBIN")


# =============================================================================
# API Key / Password Detection Tests
# =============================================================================

class TestApiKeyDetection:
    """Tests for API key and password detection."""

    def test_detect_openai_key(self):
        """Detect OpenAI-style sk- key."""
        text = "Key: sk-test1234567890abcdefghij"
        entities = detect_api_keys_passwords(text)
        assert any(e.entity_type == "api_key" for e in entities)

    def test_detect_aws_key(self):
        """Detect AWS access key."""
        text = "AWS: AKIAIOSFODNN7EXAMPLE"
        entities = detect_api_keys_passwords(text)
        assert any(e.entity_type == "api_key" for e in entities)

    def test_detect_github_token(self):
        """Detect GitHub Personal Access Token."""
        text = "Token: ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdef12"
        entities = detect_api_keys_passwords(text)
        assert any(e.entity_type == "api_key" for e in entities)

    def test_detect_password_assignment(self):
        """Detect password=value patterns."""
        text = "config: password=SuperSecret123!"
        entities = detect_api_keys_passwords(text)
        assert any(e.entity_type == "password" for e in entities)

    def test_api_key_masking(self):
        """API keys should be heavily masked."""
        text = "Key: sk-test1234567890abcdefghij"
        entities = detect_api_keys_passwords(text)
        for entity in entities:
            if entity.entity_type == "api_key":
                assert "1234567890" not in entity.masked_value


# =============================================================================
# Employee ID Detection Tests
# =============================================================================

class TestEmployeeIdDetection:
    """Tests for employee ID detection."""

    def test_detect_emp_format(self):
        """Detect EMP-YYYY-NNNN format."""
        text = "Employee: EMP-2024-0891"
        entities = detect_employee_ids(text)
        assert len(entities) >= 1
        assert entities[0].entity_type == "employee_id"

    def test_detect_simple_emp_id(self):
        """Detect simple EMP+digits format."""
        text = "ID: EMP001"
        entities = detect_employee_ids(text)
        assert len(entities) >= 1


# =============================================================================
# NLP Detector Tests
# =============================================================================

class TestNlpDetection:
    """Tests for NLP-based detection."""

    def test_detect_confidential_keywords(self):
        """Detect confidential markers in text."""
        text = "CONFIDENTIAL - This document is for internal use only."
        entities = detect_confidential_keywords(text)
        types = [e.entity_type for e in entities]
        assert "confidential_marker" in types

    def test_detect_multiple_keywords(self):
        """Detect multiple confidential keywords."""
        text = "CONFIDENTIAL and RESTRICTED content. Do not share."
        entities = detect_confidential_keywords(text)
        assert len(entities) >= 2

    def test_detect_business_sensitive(self):
        """Detect business-sensitive content."""
        text = "Revenue of INR 15,00,000 for Q3."
        entities = detect_business_sensitive(text)
        assert len(entities) >= 1

    def test_ner_entities(self):
        """Test NER detection of person names."""
        text = "Rajesh Kumar works at TestCorp Industries in Bangalore."
        entities = detect_ner_entities(text)
        entity_types = [e.entity_type for e in entities]
        # spaCy should detect at least one PERSON or ORG
        assert "person_name" in entity_types or "organization" in entity_types


# =============================================================================
# Unified Pipeline Tests
# =============================================================================

class TestUnifiedDetection:
    """Tests for the unified detection pipeline."""

    def test_unified_on_sensitive_document(self):
        """Test full pipeline on a document with multiple entity types."""
        text = """CONFIDENTIAL - Employee Record
        
Name: Rajesh Kumar
Aadhaar: 2345 6789 0123
PAN: ABCPK1234F
Email: rajesh@testcorp.in
Phone: +91 98765 43210
Employee ID: EMP-2024-0891
Credit Card: 4111 1111 1111 1111
IFSC: SBIN0001234
API Key: sk-test1234567890abcdefghij
Password: password=SuperSecret123
"""
        result = run_unified_detection(text)
        
        assert result.total_entities > 0
        assert len(result.entities) > 0
        assert "regex" in result.detection_methods
        
        # Should detect multiple entity types
        detected_types = set(result.entity_counts.keys())
        assert "email" in detected_types
        assert "pan" in detected_types

    def test_unified_on_clean_document(self):
        """Test pipeline on a document with no sensitive data."""
        text = "This is a normal document about weather and sports."
        result = run_unified_detection(text)
        
        # May still detect NER entities, but no structured PII
        regex_types = {"aadhaar", "pan", "email", "phone", "credit_card", 
                       "ifsc", "api_key", "password", "employee_id"}
        detected_regex_types = set(result.entity_counts.keys()) & regex_types
        assert len(detected_regex_types) == 0

    def test_unified_on_empty_text(self):
        """Test pipeline on empty text."""
        result = run_unified_detection("")
        assert result.total_entities == 0
        assert "note" in result.metadata

    def test_unified_no_plaintext_values(self):
        """Verify no raw sensitive values appear in output."""
        text = "PAN: ABCPK1234F\nEmail: secret@test.com"
        result = run_unified_detection(text)
        
        for entity in result.entities:
            # The masked_value should not contain the full raw value
            if entity.entity_type == "pan":
                assert "PK1234" not in entity.masked_value
            if entity.entity_type == "email":
                assert "secret" not in entity.masked_value

    def test_unified_result_structure(self):
        """Test that DetectionResult has all required fields."""
        text = "Email: test@example.com"
        result = run_unified_detection(text)
        
        assert hasattr(result, "entities")
        assert hasattr(result, "entity_counts")
        assert hasattr(result, "total_entities")
        assert hasattr(result, "detection_methods")
        assert hasattr(result, "metadata")
        
        # Test serialization
        result_dict = result.to_dict()
        assert "total_entities" in result_dict
        assert "entities" in result_dict

    def test_unified_nlp_disabled(self):
        """Test pipeline with NLP disabled."""
        text = "PAN: ABCPK1234F"
        result = run_unified_detection(text, enable_nlp=False)
        
        assert result.total_entities >= 1
        assert "nlp" not in result.detection_methods
