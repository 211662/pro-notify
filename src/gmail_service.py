"""
Gmail Service Module — DEPRECATED
This module is kept for backward compatibility.
All functionality has moved to src/email_service.py.
"""

# Re-export everything from email_service for backward compatibility
from src.email_service import EmailMessage, EmailService

# Legacy alias
GmailService = EmailService

__all__ = ["EmailMessage", "GmailService", "EmailService"]
