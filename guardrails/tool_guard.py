from typing import Dict, Any, Tuple, Optional, Set
from pydantic import BaseModel, Field
from config import MAX_TOOL_CALL_BUDGET, TOOL_TIMEOUT_SECONDS

class ToolGuardViolation(Exception):
    pass

class ToolGuard:
    ALLOWED_TOOLS: Set[str] = {
        "log_search",
        "error_classifier",
        "kb_retrieve",
        "report_tool"
    }

    def __init__(self, max_budget: int = MAX_TOOL_CALL_BUDGET, timeout_sec: int = TOOL_TIMEOUT_SECONDS):
        self.max_budget = max_budget
        self.timeout_sec = timeout_sec
        self.call_count = 0
        self.call_history: list = []

    def reset(self):
        self.call_count = 0
        self.call_history.clear()

    def validate_and_record(self, tool_name: str, arguments: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Checks tool allowlist, argument validity, and budget limits."""
        # 1. Allow-list check
        if tool_name not in self.ALLOWED_TOOLS:
            msg = f"Security Violation: Tool '{tool_name}' is not in the authorized allow-list: {self.ALLOWED_TOOLS}"
            return False, msg

        # 2. Call budget check
        if self.call_count >= self.max_budget:
            msg = f"Resource Limit: Tool call budget exceeded ({self.call_count}/{self.max_budget} calls)."
            return False, msg

        # 3. Argument checks (read-only validation, no injection into tool params)
        for k, v in arguments.items():
            if isinstance(v, str):
                if len(v) > 2000:
                    return False, f"Argument '{k}' exceeds maximum allowable length of 2000 characters."
                # Disallow shell escape / command injection sequences
                if any(bad in v for bad in ["; rm ", "&&", "||", "`", "$("]):
                    return False, f"Malicious command sequence detected in argument '{k}'."

        self.call_count += 1
        self.call_history.append({"tool": tool_name, "args": arguments})
        return True, None
