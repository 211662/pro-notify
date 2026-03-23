"""
Gmail Service Module (IMAP + App Password)
Handles email fetching via IMAP — no Google Cloud needed.
"""

import imaplib
import email
import logging
from email.header import decode_header
from dataclasses import dataclass

from bs4 import BeautifulSoup

from src.config import Config

logger = logging.getLogger(__name__)


@dataclass
class EmailMessage:
    """Represents a parsed email message."""
    id: str
    subject: str
    sender: str
    date: str
    body: str
    snippet: str


class GmailService:
    """Service to fetch emails via IMAP with App Password."""

    def __init__(self):
        self.server = Config.IMAP_SERVER
        self.port = Config.IMAP_PORT
        self.email_address = Config.EMAIL_ADDRESS
        self.app_password = Config.EMAIL_APP_PASSWORD
        self._mail: imaplib.IMAP4_SSL | None = None

    def _connect(self) -> imaplib.IMAP4_SSL:
        """Connect and login to IMAP server."""
        try:
            mail = imaplib.IMAP4_SSL(self.server, self.port)
            mail.login(self.email_address, self.app_password)
            logger.info("IMAP connected: %s@%s", self.email_address, self.server)
            return mail
        except imaplib.IMAP4.error as e:
            logger.error("IMAP login failed: %s", e)
            raise

    def _ensure_connection(self) -> imaplib.IMAP4_SSL:
        """Ensure we have an active IMAP connection, reconnect if needed."""
        if self._mail is None:
            self._mail = self._connect()
        else:
            try:
                self._mail.noop()
            except Exception:
                logger.info("IMAP connection lost, reconnecting...")
                self._mail = self._connect()
        return self._mail

    def fetch_unread_emails(self, max_results: int = 10) -> list[EmailMessage]:
        """Fetch unread emails from inbox via IMAP."""
        try:
            mail = self._ensure_connection()
            mail.select("INBOX")

            status, data = mail.search(None, "UNSEEN")
            if status != "OK" or not data[0]:
                logger.debug("No unread emails found.")
                return []

            email_ids = data[0].split()
            # Take only the latest N emails
            email_ids = email_ids[-max_results:]

            emails = []
            for eid in email_ids:
                parsed = self._fetch_email(mail, eid)
                if parsed:
                    emails.append(parsed)

            logger.info("Fetched %d unread emails.", len(emails))
            return emails

        except Exception as e:
            logger.error("Error fetching emails: %s", e)
            self._mail = None  # Force reconnect next time
            return []

    def _fetch_email(self, mail: imaplib.IMAP4_SSL, email_id: bytes) -> EmailMessage | None:
        """Fetch and parse a single email by ID."""
        try:
            status, data = mail.fetch(email_id, "(RFC822)")
            if status != "OK" or not data[0]:
                return None

            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email)

            subject = self._decode_header_value(msg.get("Subject", ""))
            sender = self._decode_header_value(msg.get("From", ""))
            date = msg.get("Date", "")
            body = self._extract_body(msg)
            snippet = body[:200].replace("\n", " ").strip()

            return EmailMessage(
                id=email_id.decode(),
                subject=subject,
                sender=sender,
                date=date,
                body=body,
                snippet=snippet,
            )

        except Exception as e:
            logger.error("Error parsing email %s: %s", email_id, e)
            return None

    def _extract_body(self, msg: email.message.Message) -> str:
        """Extract plain text body from email message."""
        body = ""

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))

                # Skip attachments
                if "attachment" in content_disposition:
                    continue

                payload = part.get_payload(decode=True)
                if payload is None:
                    continue

                charset = part.get_content_charset() or "utf-8"
                text = payload.decode(charset, errors="replace")

                if content_type == "text/plain":
                    body = text
                    break  # Prefer plain text
                elif content_type == "text/html" and not body:
                    soup = BeautifulSoup(text, "html.parser")
                    body = soup.get_text(separator="\n", strip=True)
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                text = payload.decode(charset, errors="replace")

                if msg.get_content_type() == "text/html":
                    soup = BeautifulSoup(text, "html.parser")
                    body = soup.get_text(separator="\n", strip=True)
                else:
                    body = text

        return body.strip()

    def mark_as_read(self, msg_id: str) -> None:
        """Mark an email as read (add \\Seen flag)."""
        try:
            mail = self._ensure_connection()
            mail.select("INBOX")
            mail.store(msg_id.encode(), "+FLAGS", "\\Seen")
            logger.debug("Marked email %s as read.", msg_id)
        except Exception as e:
            logger.error("Error marking email %s as read: %s", msg_id, e)

    @staticmethod
    def _decode_header_value(value: str) -> str:
        """Decode email header value (handles encoded-word syntax)."""
        if not value:
            return ""
        decoded_parts = decode_header(value)
        result = []
        for part, charset in decoded_parts:
            if isinstance(part, bytes):
                result.append(part.decode(charset or "utf-8", errors="replace"))
            else:
                result.append(part)
        return " ".join(result)
