import re
from typing import Set, List, Dict, Any, Tuple, Optional
from pydantic import BaseModel
from core.schemas import SeverityLevel
from config import MIN_CONFIDENCE_THRESHOLD

class OutputGuardResult(BaseModel):
    passed: bool
    valid_citations: List[str] = []
    hallucinated_citations: List[str] = []
    violations: List[str] = []
    sanitized_report: str
    requires_human_review: bool = False

class OutputGuard:
    CITATION_REGEX = re.compile(r'\b(L-\d{4,5})\b')
    EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b')
    CREDIT_CARD_PATTERN = re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b')

    @classmethod
    def extract_citations(cls, text: str) -> List[str]:
        return sorted(list(set(cls.CITATION_REGEX.findall(text))))

    @classmethod
    def check_citations(cls, text: str, valid_line_ids: Set[str]) -> Tuple[List[str], List[str]]:
        found = cls.extract_citations(text)
        valid = [c for c in found if c in valid_line_ids]
        hallucinated = [c for c in found if c not in valid_line_ids]
        return valid, hallucinated

    @classmethod
    def validate_report(
        cls,
        report_markdown: str,
        valid_line_ids: Set[str],
        severity_value: str,
        confidence_score: float,
        has_runbook: bool
    ) -> OutputGuardResult:
        violations = []
        requires_human = False

        # 1. Severity Enum check
        try:
            _ = SeverityLevel(severity_value)
        except ValueError:
            violations.append(f"Invalid severity value '{severity_value}'. Must be one of {[s.value for s in SeverityLevel]}")

        # 2. Citations check
        valid_citations, hallucinated_citations = cls.check_citations(report_markdown, valid_line_ids)
        if hallucinated_citations:
            violations.append(f"Grounding failure: Hallucinated log line citations found: {hallucinated_citations}")

        if not valid_citations:
            violations.append("Evidence failure: Report must cite at least one verified log line ID (e.g., L-0001).")

        # 3. Runbook remediation citation check
        if not has_runbook:
            violations.append("Grounding failure: Every remediation must cite an authorized runbook.")

        # 4. Confidence threshold check
        if confidence_score < MIN_CONFIDENCE_THRESHOLD:
            requires_human = True
            violations.append(f"Low confidence ({confidence_score:.2f} < {MIN_CONFIDENCE_THRESHOLD}): Escalated for human review.")

        # 5. Final PII scrub
        scrubbed = cls.EMAIL_PATTERN.sub("[REDACTED_EMAIL]", report_markdown)
        scrubbed = cls.CREDIT_CARD_PATTERN.sub("[REDACTED_CREDIT_CARD]", scrubbed)

        passed = len(hallucinated_citations) == 0 and len(valid_citations) > 0

        return OutputGuardResult(
            passed=passed,
            valid_citations=valid_citations,
            hallucinated_citations=hallucinated_citations,
            violations=violations,
            sanitized_report=scrubbed,
            requires_human_review=requires_human or not passed
        )
