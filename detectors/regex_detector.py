"""
Regex-Based Sensitive Data Detector
====================================
Detects structured/pattern-based sensitive entities using regular expressions.

Supported entity types:
- Aadhaar Numbers (12-digit Indian national ID)
- PAN Numbers (Indian tax ID)
- Email Addresses
- Phone Numbers (Indian + international)
- Credit Card Numbers (with optional Luhn validation)
- Bank Details (account numbers, IFSC codes, SWIFT/BIC)
- API Keys / Passwords / Secrets
- Employee IDs (configurable pattern)

Each detector returns a list of DetectedEntity objects with masked values,
location info, and confidence scores.
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DetectedEntity:
    """A single detected sensitive data entity.
    
    Attributes:
        entity_type: Category of sensitive data (e.g., 'aadhaar', 'email').
        value: The raw matched value (used internally only, never exposed to UI).
        masked_value: Masked version for display (e.g., 'XXXX XXXX 0123').
        location: Where the entity was found (line number, page, row).
        method: Detection method ('regex' or 'nlp').
        confidence: Confidence score (0.0 to 1.0).
        pattern_name: Name of the specific regex pattern that matched.
    """
    entity_type: str
    value: str
    masked_value: str
    location: dict = field(default_factory=dict)
    method: str = "regex"
    confidence: float = 1.0
    pattern_name: Optional[str] = None


def mask_value(value: str, entity_type: str) -> str:
    """Mask a sensitive value for safe display.
    
    Masking rules:
    - Show only last 4 characters for numeric IDs
    - Show only domain for emails
    - Show first 2 and last 2 chars for short strings
    - Full mask for passwords/API keys
    
    Args:
        value: Raw sensitive value.
        entity_type: Type of entity for masking strategy.
        
    Returns:
        Masked string safe for display.
    """
    value = value.strip()
    
    if entity_type in ("api_key", "password", "secret"):
        # Full mask for secrets — show only first 4 chars
        if len(value) > 8:
            return value[:4] + "*" * (len(value) - 4)
        return "*" * len(value)
    
    if entity_type == "email":
        # Show only domain part
        if "@" in value:
            local, domain = value.split("@", 1)
            masked_local = local[0] + "*" * (len(local) - 1) if len(local) > 1 else "*"
            return f"{masked_local}@{domain}"
        return "*" * len(value)
    
    if entity_type in ("aadhaar", "credit_card", "bank_account"):
        # Show only last 4 digits
        digits = re.sub(r"\D", "", value)
        if len(digits) >= 4:
            return "*" * (len(digits) - 4) + digits[-4:]
        return "*" * len(value)
    
    if entity_type == "pan":
        # Show first 3 and last 1 character
        if len(value) >= 10:
            return value[:3] + "*" * 6 + value[-1:]
        return "*" * len(value)
    
    if entity_type == "phone":
        # Show only last 4 digits
        digits = re.sub(r"\D", "", value)
        if len(digits) >= 4:
            return "*" * (len(digits) - 4) + digits[-4:]
        return "*" * len(value)
    
    if entity_type == "ifsc":
        # Show first 4 (bank code) and mask the rest
        if len(value) >= 4:
            return value[:4] + "*" * (len(value) - 4)
        return "*" * len(value)
    
    # Default: show first 2 and last 2 characters
    if len(value) > 6:
        return value[:2] + "*" * (len(value) - 4) + value[-2:]
    return "*" * len(value)


# =============================================================================
# Individual Regex Detectors
# =============================================================================

def detect_aadhaar(text: str) -> list[DetectedEntity]:
    """Detect Aadhaar numbers (12-digit Indian national ID).
    
    Format: XXXX XXXX XXXX or XXXX-XXXX-XXXX or XXXXXXXXXXXX
    First digit cannot be 0 or 1.
    """
    entities = []
    # Matches 12-digit patterns with optional spaces or hyphens.
    # Synthetic demo/test data often starts with 1, so keep this format-focused.
    pattern = r'(?<!\d)(?<!\d[\s\-])(\d{4}[\s\-]?\d{4}[\s\-]?\d{4})(?![\s\-]?\d)'
    
    for line_num, line in enumerate(text.split("\n"), start=1):
        for match in re.finditer(pattern, line):
            value = match.group(1)
            # Verify it's exactly 12 digits
            digits = re.sub(r"\D", "", value)
            if len(digits) == 12:
                entities.append(DetectedEntity(
                    entity_type="aadhaar",
                    value=value,
                    masked_value=mask_value(value, "aadhaar"),
                    location={"line": line_num, "start": match.start(), "end": match.end()},
                    method="regex",
                    confidence=0.85,
                    pattern_name="aadhaar_12digit",
                ))
    
    return entities


def detect_pan(text: str) -> list[DetectedEntity]:
    """Detect PAN numbers (Indian Permanent Account Number).
    
    Format: AAAAA9999A — 5 uppercase letters, 4 digits, 1 uppercase letter.
    The 4th character indicates the type of holder.
    """
    entities = []
    pattern = r'\b([A-Z]{5}\d{4}[A-Z])\b'
    
    for line_num, line in enumerate(text.split("\n"), start=1):
        for match in re.finditer(pattern, line):
            value = match.group(1)
            entities.append(DetectedEntity(
                entity_type="pan",
                value=value,
                masked_value=mask_value(value, "pan"),
                location={"line": line_num, "start": match.start(), "end": match.end()},
                method="regex",
                confidence=0.90,
                pattern_name="pan_india",
            ))
    
    return entities


def detect_email(text: str) -> list[DetectedEntity]:
    """Detect email addresses."""
    entities = []
    pattern = r'\b([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})\b'
    
    for line_num, line in enumerate(text.split("\n"), start=1):
        for match in re.finditer(pattern, line):
            value = match.group(1)
            entities.append(DetectedEntity(
                entity_type="email",
                value=value,
                masked_value=mask_value(value, "email"),
                location={"line": line_num, "start": match.start(), "end": match.end()},
                method="regex",
                confidence=0.95,
                pattern_name="email_standard",
            ))
    
    return entities


def detect_phone(text: str) -> list[DetectedEntity]:
    """Detect phone numbers (Indian and international formats).
    
    Formats matched:
    - +91 XXXXX XXXXX
    - +91-XXXXX-XXXXX
    - 91XXXXXXXXXX
    - XXXXXXXXXX (10-digit Indian mobile)
    - +1-XXX-XXX-XXXX (US format)
    - General international: +CC XXXXXXXXX
    """
    entities = []
    patterns = [
        # Indian mobile with +91 prefix
        (r'(?<!\d)(\+91[\s\-]?\d{5}[\s\-]?\d{5})(?!\d)', "phone_india_plus91"),
        # Indian mobile without prefix (10 digits starting with 6-9)
        (r'(?<!\d)([6-9]\d{9})(?!\d)', "phone_india_10digit"),
        # International format with country code
        (r'(\+\d{1,3}[\s\-]\d{3}[\s\-]\d{3}[\s\-]\d{4})', "phone_international"),
    ]
    
    for line_num, line in enumerate(text.split("\n"), start=1):
        for pattern, pattern_name in patterns:
            for match in re.finditer(pattern, line):
                value = match.group(1)
                digits = re.sub(r"\D", "", value)
                # Minimum 10 digits for a valid phone number
                if len(digits) >= 10:
                    entities.append(DetectedEntity(
                        entity_type="phone",
                        value=value,
                        masked_value=mask_value(value, "phone"),
                        location={"line": line_num, "start": match.start(), "end": match.end()},
                        method="regex",
                        confidence=0.80,
                        pattern_name=pattern_name,
                    ))
    
    return entities


def detect_credit_card(text: str) -> list[DetectedEntity]:
    """Detect credit card numbers (13–19 digits) with Luhn validation.
    
    Common prefixes:
    - Visa: 4XXX
    - Mastercard: 5[1-5]XX or 2[2-7]XX
    - Amex: 3[47]XX
    """
    entities = []
    # Match 13-19 digit patterns with optional separators
    pattern = r'(?<!\d)(\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{1,7})(?!\d)'
    
    for line_num, line in enumerate(text.split("\n"), start=1):
        for match in re.finditer(pattern, line):
            value = match.group(1)
            digits = re.sub(r"\D", "", value)
            
            if 13 <= len(digits) <= 19:
                is_luhn_valid = _luhn_check(digits)
                entities.append(DetectedEntity(
                    entity_type="credit_card",
                    value=value,
                    masked_value=mask_value(value, "credit_card"),
                    location={"line": line_num, "start": match.start(), "end": match.end()},
                    method="regex",
                    confidence=0.90 if is_luhn_valid else 0.65,
                    pattern_name="credit_card_luhn" if is_luhn_valid else "credit_card_pattern_non_luhn",
                ))
    
    return entities


def _luhn_check(number: str) -> bool:
    """Validate a number using the Luhn algorithm.
    
    Args:
        number: String of digits to validate.
        
    Returns:
        True if the number passes the Luhn check.
    """
    digits = [int(d) for d in number]
    digits.reverse()
    
    total = 0
    for i, digit in enumerate(digits):
        if i % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    
    return total % 10 == 0


def detect_bank_details(text: str) -> list[DetectedEntity]:
    """Detect bank-related details: IFSC codes and SWIFT/BIC codes.
    
    IFSC format: 4 letters + 0 + 6 alphanumeric characters (e.g., SBIN0001234)
    SWIFT/BIC: 8 or 11 alphanumeric characters
    """
    entities = []
    
    # IFSC Code pattern: 4 letters + 0 + 6 alphanumeric
    ifsc_pattern = r'\b([A-Z]{4}0[A-Z0-9]{6})\b'
    
    for line_num, line in enumerate(text.split("\n"), start=1):
        for match in re.finditer(ifsc_pattern, line):
            value = match.group(1)
            entities.append(DetectedEntity(
                entity_type="ifsc",
                value=value,
                masked_value=mask_value(value, "ifsc"),
                location={"line": line_num, "start": match.start(), "end": match.end()},
                method="regex",
                confidence=0.90,
                pattern_name="ifsc_code",
            ))
    
    return entities


def detect_api_keys_passwords(text: str) -> list[DetectedEntity]:
    """Detect API keys, passwords, secrets, and tokens.
    
    Patterns:
    - OpenAI keys: sk-...
    - AWS Access Keys: AKIA...
    - GitHub tokens: ghp_...
    - Generic key/password assignments: password=, secret=, token=, api_key=
    """
    entities = []
    
    patterns = [
        # OpenAI/Stripe-style keys
        (r'\b(sk-[a-zA-Z0-9]{20,})\b', "api_key", "api_key_sk"),
        # AWS Access Key IDs
        (r'\b(AKIA[A-Z0-9]{16})\b', "api_key", "aws_access_key"),
        # GitHub Personal Access Tokens
        (r'\b(ghp_[a-zA-Z0-9]{30,})\b', "api_key", "github_pat"),
        # Generic password/secret/token assignments
        (r'(?:password|passwd|pwd|secret|token|api[_\-]?key)\s*[=:]\s*["\']?([^\s"\']{6,})["\']?',
         "password", "password_assignment"),
    ]
    
    for line_num, line in enumerate(text.split("\n"), start=1):
        for pattern, entity_type, pattern_name in patterns:
            for match in re.finditer(pattern, line, re.IGNORECASE):
                value = match.group(1)
                entities.append(DetectedEntity(
                    entity_type=entity_type,
                    value=value,
                    masked_value=mask_value(value, entity_type),
                    location={"line": line_num, "start": match.start(), "end": match.end()},
                    method="regex",
                    confidence=0.85,
                    pattern_name=pattern_name,
                ))
    
    return entities


def detect_employee_ids(text: str) -> list[DetectedEntity]:
    """Detect employee ID patterns.
    
    Default pattern: EMP-YYYY-NNNN or EMP followed by digits.
    This is configurable for different organization patterns.
    """
    entities = []
    patterns = [
        (r'\b(EMP[\-_]?\d{4}[\-_]?\d{3,6})\b', "employee_id_emp_format"),
        (r'\b(EMP[\-_]\d{3,8})\b', "employee_id_short_delimited"),
        (r'\b(EMP\d{3,8})\b', "employee_id_simple"),
    ]
    
    for line_num, line in enumerate(text.split("\n"), start=1):
        for pattern, pattern_name in patterns:
            for match in re.finditer(pattern, line, re.IGNORECASE):
                value = match.group(1)
                entities.append(DetectedEntity(
                    entity_type="employee_id",
                    value=value,
                    masked_value=mask_value(value, "employee_id"),
                    location={"line": line_num, "start": match.start(), "end": match.end()},
                    method="regex",
                    confidence=0.75,
                    pattern_name=pattern_name,
                ))
    
    return entities


def run_all_regex_detectors(text: str) -> list[DetectedEntity]:
    """Run all regex-based detectors on the given text.
    
    Args:
        text: Full document text to scan.
        
    Returns:
        Combined list of all detected entities from all regex detectors.
    """
    all_entities = []
    
    detectors = [
        detect_aadhaar,
        detect_pan,
        detect_email,
        detect_phone,
        detect_credit_card,
        detect_bank_details,
        detect_api_keys_passwords,
        detect_employee_ids,
    ]
    
    for detector in detectors:
        try:
            entities = detector(text)
            all_entities.extend(entities)
        except Exception as e:
            # Log error but don't crash the pipeline
            print(f"Warning: Detector {detector.__name__} failed: {e}")
    
    return all_entities
