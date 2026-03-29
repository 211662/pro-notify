"""
Keyword Matcher Module
Scans email content for configured keywords.
"""

import re
import logging
from dataclasses import dataclass

from src.email_service import EmailMessage

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    """Result of keyword matching on an email."""
    email: EmailMessage
    matched_keywords: list[str]
    matched_in: list[str]  # Where the keyword was found: "subject", "body"

    @property
    def has_match(self) -> bool:
        return len(self.matched_keywords) > 0


class KeywordMatcher:
    """Scans email content for configured keywords and sender filters."""

    def __init__(self, keywords: list[str], sender_filters: list[str] | None = None):
        self.keywords = keywords
        self.sender_filters = [s.lower() for s in (sender_filters or [])]
        # Pre-compile regex patterns for each keyword (case-insensitive, word boundary)
        self.patterns = {
            kw: re.compile(re.escape(kw), re.IGNORECASE)
            for kw in self.keywords
        }
        logger.info(
            "KeywordMatcher initialized with %d keywords, %d sender_filters",
            len(self.keywords), len(self.sender_filters),
        )

    def _match_sender(self, sender: str) -> bool:
        """Check if sender matches any sender_filter."""
        if not self.sender_filters or not sender:
            return False
        sender_lower = sender.lower()
        return any(sf in sender_lower for sf in self.sender_filters)

    def match(self, email: EmailMessage) -> MatchResult:
        """Check if an email matches any configured keywords or sender filters."""
        matched_keywords = []
        matched_in = set()

        # 1. Check sender filters — match ALL emails from these senders
        if self._match_sender(email.sender):
            matched_keywords.append(f"sender:{email.sender}")
            matched_in.add("sender")

        # 2. Check keyword patterns in subject/body/snippet
        searchable_fields = {
            "subject": email.subject,
            "body": email.body,
            "snippet": email.snippet,
        }

        for keyword, pattern in self.patterns.items():
            for field_name, field_value in searchable_fields.items():
                if field_value and pattern.search(field_value):
                    if keyword not in matched_keywords:
                        matched_keywords.append(keyword)
                    matched_in.add(field_name)

        result = MatchResult(
            email=email,
            matched_keywords=matched_keywords,
            matched_in=sorted(matched_in),
        )

        if result.has_match:
            logger.info(
                "Email '%s' matched keywords %s in %s",
                email.subject,
                matched_keywords,
                result.matched_in,
            )
        else:
            logger.debug("Email '%s' — no keyword match.", email.subject)

        return result

    def match_many(self, emails: list[EmailMessage]) -> list[MatchResult]:
        """Match keywords against multiple emails, returning only matches."""
        results = []
        for email in emails:
            result = self.match(email)
            if result.has_match:
                results.append(result)

        logger.info(
            "Matched %d/%d emails with keywords.",
            len(results), len(emails),
        )
        return results
