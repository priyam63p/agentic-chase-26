import re
from datetime import datetime
from typing import List, Optional, Dict, Any
from core.schemas import LogEntry

class LogSearchTool:
    """Read-only log search tool supporting filtering by service, regex, level, time range, and line IDs."""

    @staticmethod
    def search(
        entries: List[LogEntry],
        service: Optional[str] = None,
        query_pattern: Optional[str] = None,
        level: Optional[str] = None,
        time_start: Optional[datetime] = None,
        time_end: Optional[datetime] = None,
        line_ids: Optional[List[str]] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        results = []
        regex = None
        if query_pattern:
            try:
                regex = re.compile(query_pattern, re.IGNORECASE)
            except re.error:
                # If regex fails, fallback to simple case-insensitive substring
                pass

        for e in entries:
            # 1. Line ID filter
            if line_ids and e.line_id not in line_ids:
                continue

            # 2. Service filter
            if service and e.service.lower() != service.lower():
                continue

            # 3. Level filter
            if level and e.level.upper() != level.upper():
                continue

            # 4. Time filter
            if time_start and e.timestamp < time_start:
                continue
            if time_end and e.timestamp > time_end:
                continue

            # 5. Pattern filter
            if query_pattern:
                if regex:
                    if not (regex.search(e.message) or regex.search(e.service)):
                        continue
                else:
                    if query_pattern.lower() not in e.message.lower():
                        continue

            results.append({
                "line_id": e.line_id,
                "timestamp": e.timestamp.isoformat(),
                "service": e.service,
                "level": e.level,
                "message": e.message
            })

            if len(results) >= limit:
                break

        return results
