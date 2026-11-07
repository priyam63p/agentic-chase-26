import re
from typing import Dict, Any

class ErrorClassifierTool:
    """Classifies error messages, log lines, or stack traces into a standard system failure taxonomy."""

    RULES = [
        ("DATABASE_FAILURE", [
            re.compile(r'(?i)(connection pool|database|postgres|mysql|query timeout|deadlock|pool exhausted|too many connections)')
        ]),
        ("MEMORY_LEAK_OOM", [
            re.compile(r'(?i)(out of memory|oom|heap space|gc overhead|exit code 137|memory leak|oomkilled)')
        ]),
        ("BAD_DEPLOYMENT", [
            re.compile(r'(?i)(deploy|release|canary|v\d+\.\d+|startup error|rollout|version mismatch)')
        ]),
        ("DISK_EXHAUSTION", [
            re.compile(r'(?i)(no space left on device|disk full|enospc|filesystem|inode exhaustion)')
        ]),
        ("CACHE_WARNING", [
            re.compile(r'(?i)(cache miss|redis eviction|cache timeout|stale cache|ttl expired)')
        ]),
        ("NETWORK_GATEWAY_TIMEOUT", [
            re.compile(r'(?i)(504 gateway timeout|upstream timeout|connection refused|socket reset)')
        ])
    ]

    @classmethod
    def classify(cls, error_text: str) -> Dict[str, Any]:
        matched_category = "GENERIC_ERROR"
        confidence = 0.5
        explanation = "Error message did not strongly match specific operational failure patterns."

        for category, patterns in cls.RULES:
            for pat in patterns:
                m = pat.search(error_text)
                if m:
                    matched_category = category
                    confidence = 0.92
                    explanation = f"Matched diagnostic pattern: '{m.group(0)}'"
                    return {
                        "category": matched_category,
                        "confidence": confidence,
                        "explanation": explanation
                    }

        return {
            "category": matched_category,
            "confidence": confidence,
            "explanation": explanation
        }
