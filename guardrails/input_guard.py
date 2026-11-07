import re
from pathlib import Path
from typing import Tuple, List, Dict, Any, Optional
from pydantic import BaseModel
from config import MAX_FILE_SIZE_BYTES, MAX_LOG_LINES, ALLOWED_EXTENSIONS

class InputGuardResult(BaseModel):
    passed: bool
    sanitized_content: str
    violations: List[str] = []
    quarantined_lines: List[Dict[str, Any]] = []
    pii_redaction_count: int = 0
    injection_detected: bool = False

class InputGuard:
    # Common PII Regex Patterns
    EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b')
    SECRET_PATTERN = re.compile(r'(?i)(password|secret|bearer\s+|api[_-]?key|token)\s*[:=]\s*["'']?([a-zA-Z0-9_\-\.]{8,})["'']?')
    CREDIT_CARD_PATTERN = re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b')
    SSN_PATTERN = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')

    # Injection Patterns
    INJECTION_PATTERNS = [
        re.compile(r'(?i)ignore\s+(all\s+)?(previous|prior)\s+instructions'),
        re.compile(r'(?i)system\s+prompt'),
        re.compile(r'(?i)mark\s+(this\s+as\s+|as\s+)?(low|negligible|resolved)'),
        re.compile(r'(?i)override\s+severity'),
        re.compile(r'(?i)disregard\s+(the\s+above|all\s+rules)'),
        re.compile(r'(?i)you\s+are\s+now\s+in\s+developer\s+mode'),
        re.compile(r'(?i)bypass\s+guardrails')
    ]

    @classmethod
    def validate_file(cls, file_path: Path) -> Tuple[bool, Optional[str]]:
        """Validates file existence, extension, and size limits."""
        if not file_path.exists():
            return False, f"File does not exist: {file_path}"
        if file_path.suffix.lower() not in ALLOWED_EXTENSIONS:
            return False, f"Unsupported file extension {file_path.suffix}. Allowed: {ALLOWED_EXTENSIONS}"
        size = file_path.stat().st_size
        if size > MAX_FILE_SIZE_BYTES:
            return False, f"File size {size} exceeds limit of {MAX_FILE_SIZE_BYTES} bytes."
        return True, None

    @classmethod
    def process_text(cls, raw_text: str) -> InputGuardResult:
        """Runs size checks, line count limits, PII redaction, and injection scanning."""
        violations = []
        quarantined = []
        pii_count = 0
        injection_found = False

        if not raw_text.strip():
            return InputGuardResult(passed=False, sanitized_content="", violations=["Input text is empty."])

        lines = raw_text.splitlines()
        if len(lines) > MAX_LOG_LINES:
            violations.append(f"Line count {len(lines)} exceeds limit of {MAX_LOG_LINES}.")
            lines = lines[:MAX_LOG_LINES]

        sanitized_lines = []
        for idx, line in enumerate(lines, start=1):
            is_malicious = False
            # 1. Injection Scan
            for pat in cls.INJECTION_PATTERNS:
                if pat.search(line):
                    is_malicious = True
                    injection_found = True
                    quarantined.append({
                        "line_number": idx,
                        "raw_line": line,
                        "reason": f"Prompt injection pattern detected: {pat.pattern}"
                    })
                    violations.append(f"Line {idx}: Prompt injection pattern detected.")
                    # Sanitize the adversarial line so it cannot poison the LLM context
                    line = f"[QUARANTINED_INJECTION_ATTEMPT: Original line {idx} neutralized]"
                    break

            # 2. PII Redaction
            emails = cls.EMAIL_PATTERN.findall(line)
            if emails:
                pii_count += len(emails)
                line = cls.EMAIL_PATTERN.sub("[REDACTED_EMAIL]", line)

            secrets = cls.SECRET_PATTERN.findall(line)
            if secrets:
                pii_count += len(secrets)
                line = cls.SECRET_PATTERN.sub(r"\1=[REDACTED_SECRET]", line)

            ccs = cls.CREDIT_CARD_PATTERN.findall(line)
            if ccs:
                pii_count += len(ccs)
                line = cls.CREDIT_CARD_PATTERN.sub("[REDACTED_CREDIT_CARD]", line)

            ssns = cls.SSN_PATTERN.findall(line)
            if ssns:
                pii_count += len(ssns)
                line = cls.SSN_PATTERN.sub("[REDACTED_SSN]", line)

            sanitized_lines.append(line)

        sanitized_content = "\n".join(sanitized_lines)
        passed = len(violations) == 0 or (injection_found and len(sanitized_lines) > 0)

        return InputGuardResult(
            passed=passed,
            sanitized_content=sanitized_content,
            violations=violations,
            quarantined_lines=quarantined,
            pii_redaction_count=pii_count,
            injection_detected=injection_found
        )
