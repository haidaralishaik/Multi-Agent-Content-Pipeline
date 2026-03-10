"""
Content Guardrails - Input validation, PII detection, and safety checks

Provides defense-in-depth for the content pipeline:
- Input validation (length, emptiness, prompt injection)
- PII detection and redaction (email, phone, SSN, credit card)
- Output scanning for leaked PII
"""

import re
from typing import Dict, List, Tuple
from dataclasses import dataclass, field
from enum import Enum


class RiskLevel(Enum):
    SAFE = "safe"
    WARNING = "warning"
    BLOCKED = "blocked"


@dataclass
class GuardrailResult:
    """Result of a guardrail check"""
    risk_level: RiskLevel
    passed: bool
    flags: List[str] = field(default_factory=list)
    pii_detected: List[Dict[str, str]] = field(default_factory=list)
    sanitized_text: str = ""


class ContentGuardrails:
    """
    Input/output guardrails for the content pipeline.

    Checks for:
    - Prompt injection attempts
    - PII in input/output (emails, phones, SSNs, credit cards)
    - Invalid or empty input
    - Excessive input length
    """

    # PII regex patterns
    PII_PATTERNS = {
        'email': r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
        'phone_us': r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',
        'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
        'credit_card': r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
        'ip_address': r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
    }

    # Prompt injection patterns (case-insensitive)
    INJECTION_PATTERNS = [
        r'ignore\s+(?:all\s+)?previous\s+instructions',
        r'disregard\s+(?:all\s+)?(?:above|previous)',
        r'you\s+are\s+now\s+(?:a|an)\b',
        r'new\s+system\s+prompt',
        r'pretend\s+you\s+are',
        r'override\s+(?:your\s+)?instructions',
        r'forget\s+(?:all\s+)?(?:your\s+)?(?:previous\s+)?instructions',
        r'act\s+as\s+(?:a|an)\s+(?:different|new)',
    ]

    MAX_TOPIC_LENGTH = 500
    MAX_NOTES_LENGTH = 5000

    def validate_input(self, topic: str, user_notes: str = "") -> GuardrailResult:
        """
        Validate user input before pipeline runs.

        Checks: empty input, length limits, prompt injection, PII.
        """
        flags = []
        pii_found = []
        risk = RiskLevel.SAFE

        # Empty check
        if not topic or not topic.strip():
            return GuardrailResult(
                risk_level=RiskLevel.BLOCKED,
                passed=False,
                flags=["Topic is empty"],
            )

        # Length checks
        if len(topic) > self.MAX_TOPIC_LENGTH:
            flags.append(f"Topic exceeds {self.MAX_TOPIC_LENGTH} characters")
            risk = RiskLevel.WARNING

        if len(user_notes) > self.MAX_NOTES_LENGTH:
            flags.append(f"Notes exceed {self.MAX_NOTES_LENGTH} characters")
            risk = RiskLevel.WARNING

        # Prompt injection check
        combined_text = f"{topic} {user_notes}"
        injection_detected, injection_flags = self.check_prompt_injection(combined_text)
        if injection_detected:
            return GuardrailResult(
                risk_level=RiskLevel.BLOCKED,
                passed=False,
                flags=[f"Prompt injection detected: {f}" for f in injection_flags],
            )

        # PII check on input
        pii_found = self.detect_pii(combined_text)
        if pii_found:
            flags.append(f"PII detected in input: {len(pii_found)} item(s)")
            risk = RiskLevel.WARNING

        passed = risk != RiskLevel.BLOCKED
        return GuardrailResult(
            risk_level=risk,
            passed=passed,
            flags=flags,
            pii_detected=pii_found,
            sanitized_text=self.redact_pii(combined_text) if pii_found else combined_text,
        )

    def scan_output(self, content: str) -> GuardrailResult:
        """
        Scan agent output for PII leakage.

        Called after pipeline completes to check final content.
        """
        flags = []
        risk = RiskLevel.SAFE

        if not content:
            return GuardrailResult(risk_level=RiskLevel.SAFE, passed=True)

        pii_found = self.detect_pii(content)
        if pii_found:
            flags.append(f"PII found in output: {len(pii_found)} item(s)")
            risk = RiskLevel.WARNING

        return GuardrailResult(
            risk_level=risk,
            passed=True,
            flags=flags,
            pii_detected=pii_found,
            sanitized_text=self.redact_pii(content) if pii_found else content,
        )

    def detect_pii(self, text: str) -> List[Dict[str, str]]:
        """Find PII patterns in text."""
        found = []
        for pii_type, pattern in self.PII_PATTERNS.items():
            for match in re.finditer(pattern, text):
                found.append({
                    'type': pii_type,
                    'value': match.group(),
                    'position': match.start(),
                })
        return found

    def redact_pii(self, text: str) -> str:
        """Replace detected PII with redaction markers."""
        result = text
        for pii_type, pattern in self.PII_PATTERNS.items():
            label = pii_type.upper().replace('_', ' ')
            result = re.sub(pattern, f'[REDACTED {label}]', result)
        return result

    def check_prompt_injection(self, text: str) -> Tuple[bool, List[str]]:
        """Check for prompt injection attempts."""
        matched = []
        lower_text = text.lower()
        for pattern in self.INJECTION_PATTERNS:
            if re.search(pattern, lower_text):
                matched.append(pattern)
        return (len(matched) > 0, matched)
