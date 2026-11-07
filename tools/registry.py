from typing import Dict, Any, List, Optional, Tuple
from guardrails.tool_guard import ToolGuard
from tools.log_search import LogSearchTool
from tools.error_classifier import ErrorClassifierTool
from tools.kb_retrieve import KBRetrieveTool
from tools.report_tool import ReportTool
from core.schemas import LogEntry

class ToolRegistry:
    """Central registry and guarded execution dispatcher for all agent tools."""

    def __init__(self, entries: Optional[List[LogEntry]] = None):
        self.entries = entries or []
        self.guard = ToolGuard()

    def set_entries(self, entries: List[LogEntry]):
        self.entries = entries

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Returns tool schema definitions for LLM tool calling."""
        return [
            {
                "name": "log_search",
                "description": "Search log entries by service, regex pattern, level, or time range.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "service": {"type": "string", "description": "Target service name"},
                        "query_pattern": {"type": "string", "description": "Regex or keyword to search in message"},
                        "level": {"type": "string", "description": "Log level (INFO, ERROR, WARN, etc.)"},
                        "limit": {"type": "integer", "description": "Max entries to return (default 20)"}
                    }
                }
            },
            {
                "name": "error_classifier",
                "description": "Classify an error string or log message into standard failure taxonomy.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "error_text": {"type": "string", "description": "The error message to classify"}
                    },
                    "required": ["error_text"]
                }
            },
            {
                "name": "kb_retrieve",
                "description": "Retrieve verified runbooks and past incident memories relevant to symptoms.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Incident symptom or query keywords"},
                        "target": {"type": "string", "enum": ["all", "runbooks", "incidents"], "description": "Target KB"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "report_tool",
                "description": "Format and structure incident summary and evidence sections.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "root_cause_service": {"type": "string"},
                        "primary_evidence": {"type": "array", "items": {"type": "string"}},
                        "impacted_services": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["title", "root_cause_service"]
                }
            }
        ]

    def execute(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Validates tool call through ToolGuard and dispatches execution."""
        is_valid, error_msg = self.guard.validate_and_record(tool_name, arguments)
        if not is_valid:
            return {
                "success": False,
                "error": error_msg,
                "tool_name": tool_name
            }

        try:
            if tool_name == "log_search":
                res = LogSearchTool.search(
                    entries=self.entries,
                    service=arguments.get("service"),
                    query_pattern=arguments.get("query_pattern"),
                    level=arguments.get("level"),
                    limit=int(arguments.get("limit", 20))
                )
                return {"success": True, "results": res, "count": len(res)}

            elif tool_name == "error_classifier":
                res = ErrorClassifierTool.classify(arguments.get("error_text", ""))
                return {"success": True, "classification": res}

            elif tool_name == "kb_retrieve":
                res = KBRetrieveTool.retrieve(
                    query=arguments.get("query", ""),
                    target=arguments.get("target", "all")
                )
                return {"success": True, "knowledge": res}

            elif tool_name == "report_tool":
                res = ReportTool.structure_summary(
                    title=arguments.get("title", ""),
                    root_cause_service=arguments.get("root_cause_service", ""),
                    primary_evidence=arguments.get("primary_evidence", []),
                    impacted_services=arguments.get("impacted_services", [])
                )
                return {"success": True, "summary": res}

            return {"success": False, "error": f"Unhandled tool '{tool_name}'"}

        except Exception as e:
            return {"success": False, "error": f"Execution error in tool '{tool_name}': {str(e)}"}
