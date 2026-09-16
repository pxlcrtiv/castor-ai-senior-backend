"""Prompt injection detection and sensitive data protection.

Middleware layer that validates user inputs before they reach the LLM,
preventing prompt injection attacks and unauthorized data access.
"""

import re
from dataclasses import dataclass

from src.config.settings import settings


@dataclass
class ValidationResult:
    """Result of prompt validation."""

    is_safe: bool
    reason: str | None = None
    blocked_keywords: list[str] | None = None


class PromptValidator:
    """Detects prompt injection attempts and sensitive data requests."""

    # Patterns that indicate prompt injection
    INJECTION_PATTERNS = [
        r"(?i)ignore\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?)",
        r"(?i)you\s+are\s+now\s+(a|an)\s+",
        r"(?i)act\s+as\s+(?:if\s+)?(?:you\s+are\s+)?",
        r"(?i)pretend\s+(?:you\s+are|to\s+be)\s+",
        r"(?i)disregard\s+(all\s+)?(previous|prior)",
        r"(?i)new\s+instructions?:",
        r"(?i)system\s*(prompt|message)\s*:",
        r"(?i)<\|system\|>",
        r"(?i)DAN\s+mode",
        r"(?i)jailbreak",
        r"(?i)bypass\s+(?:all\s+)?(?:safety|security|filters?)",
    ]

    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        r"(?i)(DROP|DELETE|UPDATE|INSERT)\s+TABLE",
        r"(?i)UNION\s+(ALL\s+)?SELECT",
        r"(?i);\s*(DROP|DELETE|UPDATE|INSERT)",
        r"(?i)--\s*$",
        r"(?i)'\s*OR\s+'1'\s*=\s*'1",
    ]

    def __init__(self, sensitive_keywords: list[str] | None = None):
        self.sensitive_keywords = sensitive_keywords or settings.sensitive_keywords
        self._injection_re = [re.compile(p) for p in self.INJECTION_PATTERNS]
        self._sql_injection_re = [re.compile(p) for p in self.SQL_INJECTION_PATTERNS]

    def validate(self, user_input: str, user_role: str = "viewer") -> ValidationResult:
        """Validate user input for security threats.

        Args:
            user_input: The raw user prompt.
            user_role: Role of the user (viewer, analyst, admin).

        Returns:
            ValidationResult with safety status and details.
        """
        # Check for prompt injection
        for pattern in self._injection_re:
            if pattern.search(user_input):
                return ValidationResult(
                    is_safe=False,
                    reason="Prompt injection attempt detected",
                    blocked_keywords=[pattern.pattern],
                )

        # Check for SQL injection
        for pattern in self._sql_injection_re:
            if pattern.search(user_input):
                return ValidationResult(
                    is_safe=False,
                    reason="SQL injection attempt detected",
                    blocked_keywords=[pattern.pattern],
                )

        # Check for sensitive data requests based on role
        if user_role in ("viewer",):
            found = self._check_sensitive_keywords(user_input)
            if found:
                return ValidationResult(
                    is_safe=False,
                    reason=f"User role '{user_role}' cannot access sensitive data",
                    blocked_keywords=found,
                )

        return ValidationResult(is_safe=True)

    def _check_sensitive_keywords(self, text: str) -> list[str]:
        """Check if text contains sensitive keywords."""
        text_lower = text.lower()
        return [kw for kw in self.sensitive_keywords if kw.lower() in text_lower]

    def sanitize_output(self, output: str) -> str:
        """Remove potentially sensitive data from LLM output.

        Args:
            output: Raw LLM response.

        Returns:
            Sanitized output with sensitive patterns masked.
        """
        # Mask email addresses
        output = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "***@***.***", output)

        # Mask phone numbers (Mexican format)
        output = re.sub(r"\+?52\s?\d{2}\s?\d{4}\s?\d{4}", "***PHONE***", output)

        # Mask RFC (Mexican tax ID)
        output = re.sub(r"\b[A-Z]{3,4}\d{6}[A-Z0-9]{3}\b", "***RFC***", output)

        return output


# Global validator instance
prompt_validator = PromptValidator()
