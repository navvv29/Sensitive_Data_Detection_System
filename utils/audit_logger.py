"""
Audit Logger Utility
====================
Logs document processing events for compliance and tracking purposes,
without logging any raw sensitive data (PII/PHI).
"""
import logging
import os
from datetime import datetime

# Configure the audit logger
audit_logger = logging.getLogger("audit_logger")
audit_logger.setLevel(logging.INFO)

# Ensure logs directory exists
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "audit.log")

file_handler = logging.FileHandler(log_file)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
audit_logger.addHandler(file_handler)

def log_document_processing(
    filename: str, 
    file_type: str, 
    total_entities: int, 
    risk_level: str, 
    risk_score: float
):
    """
    Log a document processing event securely.
    
    Args:
        filename: Name of the processed file.
        file_type: Type of the file (pdf, txt, csv).
        total_entities: Number of sensitive entities detected.
        risk_level: Assigned risk level (LOW, MEDIUM, HIGH).
        risk_score: Calculated risk score.
    """
    message = (
        f"Document Processed | "
        f"File: {filename} | Type: {file_type.upper()} | "
        f"Entities Found: {total_entities} | "
        f"Risk Level: {risk_level} | Score: {risk_score:.1f}"
    )
    audit_logger.info(message)

def log_security_event(event_type: str, details: str):
    """
    Log a specific security-related event.
    """
    audit_logger.warning(f"Security Event: {event_type} | Details: {details}")
