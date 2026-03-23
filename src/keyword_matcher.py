"""
Keyword Matcher Module
Scans email content for configured keywords.
"""

import re
import logging
from dataclasses import dataclass

from src.config import Config
from src.gmail_service import EmailMessage

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
    """Scans email content for configured keywords."""

    def __init__(self, keywords: list[str] | None = None):
        self.keywords = keywords or Config.KEYWORDS
        # Pre-compile regex patterns for each keyword (case-insensitive, word boundary)
        self.patterns = {
            kw: re.compile(re.escape(kw), re.IGNORECASE)
            for kw in self.keywords
        }
        logger.info("KeywordMatcher initialized with %d keywords: %s", len(self.keywords), self.keywords)

    def match(self, email: EmailMessage) -> MatchResult:
        """Check if an email matches any configured keywords."""
        matched_keywords = []
        matched_in = set()

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
