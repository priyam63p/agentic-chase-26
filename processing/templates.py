import re
from typing import List, Dict
from core.schemas import LogEntry, LogTemplate

class TemplateMiner:
    """Extracts generalized log patterns by masking dynamic values (IPs, numbers, UUIDs, hashes, strings)."""

    REPLACEMENTS = [
        # IP addresses (with optional port)
        (re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b'), '<IP>'),
        # UUIDs
        (re.compile(r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b'), '<UUID>'),
        # Hex addresses / hashes
        (re.compile(r'\b(?:0x[0-9a-fA-F]+|[0-9a-fA-F]{16,64})\b'), '<HEX>'),
        # File paths or URLs
        (re.compile(r'https?://[^\s]+|/(?:[\w\.\-]+/)+[\w\.\-]+'), '<PATH>'),
        # Quoted strings
        (re.compile(r'"[^"]*"|\'[^\']*\''), '<STR>'),
        # Durations and numbers with units
        (re.compile(r'\b\d+(?:\.\d+)?(?:ms|s|m|h|MB|GB|KB|B|%)\b', re.IGNORECASE), '<NUM_UNIT>'),
        # Generic integers/floats
        (re.compile(r'\b\d+(?:\.\d+)?\b'), '<NUM>')
    ]

    @classmethod
    def extract_pattern(cls, message: str) -> str:
        pattern = message
        for regex, placeholder in cls.REPLACEMENTS:
            pattern = regex.sub(placeholder, pattern)
        # Collapse multiple whitespace
        return re.sub(r'\s+', ' ', pattern).strip()

    @classmethod
    def mine(cls, entries: List[LogEntry], max_templates: int = 30) -> List[LogTemplate]:
        template_map: Dict[str, Dict] = {}

        for entry in entries:
            pat = cls.extract_pattern(entry.message)
            entry.template = pat

            if pat not in template_map:
                template_map[pat] = {
                    "count": 0,
                    "sample_line_ids": []
                }
            template_map[pat]["count"] += 1
            if len(template_map[pat]["sample_line_ids"]) < 5:
                template_map[pat]["sample_line_ids"].append(entry.line_id)

        # Sort by frequency descending
        sorted_patterns = sorted(template_map.items(), key=lambda x: x[1]["count"], reverse=True)

        templates: List[LogTemplate] = []
        for idx, (pat, data) in enumerate(sorted_patterns[:max_templates], start=1):
            templates.append(LogTemplate(
                template_id=f"T-{idx:03d}",
                pattern=pat,
                count=data["count"],
                sample_line_ids=data["sample_line_ids"]
            ))

        return templates
