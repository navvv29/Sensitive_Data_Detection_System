"""
Compliance Summary Generator
==============================
Generates AI-powered compliance summaries grounded in actual detection
and classification results. The summary includes:

1. Compliance observations — regulations/policies implicated
2. Security risks — what could go wrong if document is leaked
3. Suggested remediation steps — concrete, actionable guidance

The LLM prompt is carefully constructed to ground the summary in
the structured detection data, preventing hallucination.
"""

from typing import Optional

from detectors.unified_detector import DetectionResult
from classifiers.risk_classifier import RiskClassification
from summarizers.llm_client import LLMClient


# Regulation mapping — which regulations apply to which entity types
REGULATION_MAP = {
    "aadhaar": ["DPDP Act 2023 (India)", "Aadhaar Act 2016"],
    "pan": ["DPDP Act 2023 (India)", "Income Tax Act"],
    "credit_card": ["PCI-DSS", "DPDP Act 2023 (India)"],
    "email": ["DPDP Act 2023 (India)", "GDPR (if EU data subjects)"],
    "phone": ["DPDP Act 2023 (India)", "TCPA (if US numbers)"],
    "api_key": ["SOC 2", "ISO 27001", "Organization Security Policy"],
    "password": ["SOC 2", "ISO 27001", "Organization Security Policy"],
    "ifsc": ["RBI Guidelines", "DPDP Act 2023 (India)"],
    "bank_account": ["RBI Guidelines", "DPDP Act 2023 (India)"],
    "person_name": ["DPDP Act 2023 (India)", "GDPR (if EU data subjects)"],
    "employee_id": ["DPDP Act 2023 (India)", "Organization HR Policy"],
    "confidential_marker": ["Organization Classification Policy", "NDA Terms"],
    "business_sensitive": ["Trade Secret Law", "Organization IP Policy"],
}


SYSTEM_INSTRUCTION = """You are a data protection and compliance expert assistant.
Your role is to analyze sensitive data detection results and provide actionable
compliance and security guidance.

Rules:
- Be specific and actionable — avoid vague recommendations
- Reference actual regulations and standards by name
- Ground all observations in the detection data provided — do not invent entities
- NEVER include or repeat any raw sensitive values (PII, keys, etc.)
- Use masked values only if referencing specific findings
- Structure your response with clear headers and bullet points
- Keep the summary professional but accessible
"""


def generate_compliance_summary(
    detection_result: DetectionResult,
    risk_classification: RiskClassification,
    llm_client: Optional[LLMClient] = None,
) -> str:
    """Generate an AI-powered compliance summary.
    
    Constructs a grounded prompt from detection + classification data
    and sends it to the LLM for summary generation. Falls back to a
    template-based summary if the LLM is unavailable.
    
    Args:
        detection_result: Output from the unified detection pipeline.
        risk_classification: Output from the risk classifier.
        llm_client: Optional pre-configured LLM client.
        
    Returns:
        Formatted compliance summary string.
    """
    # Build the grounding context from structured results
    context = _build_grounding_context(detection_result, risk_classification)
    
    # Try LLM-generated summary
    if llm_client is not None:
        prompt = _build_prompt(context)
        summary = llm_client.generate(
            prompt=prompt,
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.3,
        )
        
        # Check if generation failed (fallback message)
        if not summary.startswith("⚠️"):
            return summary
    
    # Fallback: template-based summary (still grounded in detection data)
    return _generate_template_summary(context, detection_result, risk_classification)


def _build_grounding_context(
    detection_result: DetectionResult,
    risk_classification: RiskClassification,
) -> dict:
    """Build structured context for the LLM prompt.
    
    This ensures the LLM summary is grounded in actual findings,
    not hallucinated content.
    
    Args:
        detection_result: Detection pipeline output.
        risk_classification: Risk classification output.
        
    Returns:
        Dictionary with structured context for prompt construction.
    """
    # Determine applicable regulations
    applicable_regulations = set()
    for entity_type in detection_result.entity_counts:
        regs = REGULATION_MAP.get(entity_type, [])
        applicable_regulations.update(regs)
    
    # Build entity summary (masked, no raw values)
    entity_summary = []
    for entity_type, count in detection_result.entity_counts.items():
        entity_summary.append(f"- {entity_type.replace('_', ' ').title()}: {count} found")
    
    return {
        "risk_level": risk_classification.risk_level,
        "risk_score": risk_classification.risk_score,
        "total_entities": detection_result.total_entities,
        "entity_summary": "\n".join(entity_summary) if entity_summary else "No entities detected",
        "applicable_regulations": list(applicable_regulations),
        "top_risk_factors": risk_classification.top_risk_factors,
        "rationale": risk_classification.rationale,
    }


def _build_prompt(context: dict) -> str:
    """Build the LLM prompt grounded in detection context.
    
    Args:
        context: Structured context from _build_grounding_context.
        
    Returns:
        Formatted prompt string.
    """
    regulations_str = ", ".join(context["applicable_regulations"]) if context["applicable_regulations"] else "None identified"
    
    prompt = f"""Analyze the following document sensitivity detection results and provide a compliance summary.

## Detection Results

**Risk Level:** {context['risk_level']} (Score: {context['risk_score']:.0f})
**Total Sensitive Entities Found:** {context['total_entities']}

### Entities Detected:
{context['entity_summary']}

### Potentially Applicable Regulations:
{regulations_str}

### Risk Assessment:
{context['rationale']}

---

Based on ONLY the above detection results, please provide:

### 1. Compliance Observations
What regulations, standards, or policies are implicated by the detected entities? Be specific about which entity types trigger which regulations.

### 2. Security Risks  
What could go wrong if this document were leaked, mishandled, or accessed by unauthorized parties? Describe concrete threat scenarios tied to the specific entity types found.

### 3. Suggested Remediation Steps
Provide specific, actionable steps to reduce the risk. These should be prioritized and practical.

IMPORTANT: Do NOT mention or repeat any raw sensitive values. Reference entity types and counts only.
"""
    return prompt


def _generate_template_summary(
    context: dict,
    detection_result: DetectionResult,
    risk_classification: RiskClassification,
) -> str:
    """Generate a template-based fallback summary when LLM is unavailable.
    
    This is still grounded in detection data, just not as nuanced
    as an LLM-generated summary.
    
    Args:
        context: Structured context.
        detection_result: Detection output.
        risk_classification: Classification output.
        
    Returns:
        Formatted template summary string.
    """
    lines = [
        f"# Compliance Summary",
        f"",
        f"**Risk Level: {context['risk_level']}** (Score: {context['risk_score']:.0f})",
        f"**Total Sensitive Entities: {context['total_entities']}**",
        f"",
    ]
    
    # Section 1: Compliance Observations
    lines.append("## 1. Compliance Observations")
    lines.append("")
    
    if context["applicable_regulations"]:
        lines.append("The following regulations and standards may be implicated:")
        for reg in sorted(context["applicable_regulations"]):
            lines.append(f"- **{reg}**")
    else:
        lines.append("No specific regulatory implications identified.")
    lines.append("")
    
    # Section 2: Security Risks
    lines.append("## 2. Security Risks")
    lines.append("")
    
    risk_descriptions = {
        "aadhaar": "Identity theft and fraudulent authentication using Aadhaar numbers",
        "pan": "Tax fraud and financial identity theft using PAN details",
        "credit_card": "Financial fraud and unauthorized transactions",
        "api_key": "Unauthorized system access and data breaches via exposed API keys",
        "password": "Account compromise through exposed credentials",
        "phone": "Social engineering attacks and spam targeting",
        "email": "Phishing attacks and spam targeting",
        "ifsc": "Unauthorized bank transactions using exposed IFSC codes",
        "employee_id": "Internal system access misuse",
        "person_name": "Privacy violation and targeted social engineering",
        "confidential_marker": "Breach of confidentiality obligations",
        "business_sensitive": "Competitive intelligence leak and trade secret exposure",
    }
    
    for entity_type in detection_result.entity_counts:
        desc = risk_descriptions.get(entity_type)
        if desc:
            lines.append(f"- **{entity_type.replace('_', ' ').title()}**: {desc}")
    lines.append("")
    
    # Section 3: Remediation Steps
    lines.append("## 3. Suggested Remediation Steps")
    lines.append("")
    
    if context["risk_level"] == "HIGH":
        lines.extend([
            "1. **Immediate**: Restrict access to this document to authorized personnel only",
            "2. **Redact**: Remove or mask all detected PII before sharing externally",
            "3. **Rotate**: If API keys or passwords were exposed, rotate them immediately",
            "4. **Encrypt**: Store this document with encryption at rest",
            "5. **Audit**: Log all access to this document and review access controls",
            "6. **Notify**: Consider notifying affected individuals per DPDP Act requirements",
        ])
    elif context["risk_level"] == "MEDIUM":
        lines.extend([
            "1. **Restrict**: Limit document access to need-to-know personnel",
            "2. **Redact**: Consider masking sensitive fields before wider distribution",
            "3. **Label**: Ensure the document is properly classified as sensitive",
            "4. **Review**: Periodically review who has access to this document",
        ])
    else:
        lines.extend([
            "1. **Standard handling**: Follow normal document management procedures",
            "2. **Monitor**: Continue periodic reviews of document content",
        ])
    
    lines.append("")
    lines.append("---")
    lines.append("*Note: This is a template-based summary. For enhanced analysis, configure an LLM API key.*")
    
    return "\n".join(lines)
