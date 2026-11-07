import csv
import io
import json
import re
from datetime import datetime
from typing import List, Optional, Any
from core.schemas import LogEntry

class LogParser:
    """Parses TXT, JSON, and CSV log sources into normalized LogEntry objects with stable L-XXXX IDs."""

    TIMESTAMP_PATTERNS = [
        (re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?"), "%Y-%m-%d %H:%M:%S"),
        (re.compile(r"^\d{4}/\d{2}/\d{2}[T ]\d{2}:\d{2}:\d{2}"), "%Y/%m/%d %H:%M:%S")
    ]

    LOG_LINE_REGEX = re.compile(
        r"^(?P<timestamp>\d{4}[-/]\d{2}[-/]\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\s+"
        r"(?:\[?(?P<service>[a-zA-Z0-9_\-\.]+)\]?)\s+"
        r"(?:\[?(?P<level>DEBUG|INFO|WARN|WARNING|ERROR|CRITICAL|FATAL)\]?)\s*:?\s*"
        r"(?P<message>.*)$",
        re.IGNORECASE
    )

    @classmethod
    def parse_content(cls, content: str, file_type: Optional[str] = None) -> List[LogEntry]:
        content = content.strip()
        if not content:
            return []

        # Auto-detect format if not explicitly provided
        if not file_type:
            if content.startswith("[") or (content.startswith("{") and "}" in content):
                file_type = "json"
            elif "," in content.splitlines()[0] and any(col in content.splitlines()[0].lower() for col in ["service", "level", "message", "timestamp"]):
                file_type = "csv"
            else:
                file_type = "txt"

        if file_type == "json":
            return cls._parse_json(content)
        elif file_type == "csv":
            return cls._parse_csv(content)
        else:
            return cls._parse_txt(content)

    @classmethod
    def _parse_timestamp(cls, ts_str: Any) -> datetime:
        if isinstance(ts_str, (int, float)):
            # unix timestamp in seconds or ms
            if ts_str > 1e11:
                return datetime.fromtimestamp(ts_str / 1000.0)
            return datetime.fromtimestamp(ts_str)
        if isinstance(ts_str, datetime):
            return ts_str

        ts_clean = str(ts_str).strip()
        # Clean ISO 'Z' or timezone for simple parsing
        ts_clean = ts_clean.replace("Z", "").replace("T", " ")
        if "." in ts_clean:
            ts_clean = ts_clean.split(".")[0]

        for fmt in ["%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d"]:
            try:
                return datetime.strptime(ts_clean, fmt)
            except ValueError:
                pass
        return datetime.utcnow()

    @classmethod
    def _parse_json(cls, content: str) -> List[LogEntry]:
        entries: List[LogEntry] = []
        raw_items = []
        try:
            parsed = json.loads(content)
            if isinstance(parsed, list):
                raw_items = parsed
            elif isinstance(parsed, dict):
                raw_items = [parsed]
        except json.JSONDecodeError:
            # Try JSON Lines
            for line in content.splitlines():
                line = line.strip()
                if line:
                    try:
                        raw_items.append(json.loads(line))
                    except Exception:
                        pass

        for idx, item in enumerate(raw_items, start=1):
            line_id = f"L-{idx:04d}"
            ts = cls._parse_timestamp(item.get("timestamp") or item.get("time") or datetime.utcnow())
            service = str(item.get("service") or item.get("app") or item.get("component") or "unknown-service")
            level = str(item.get("level") or item.get("severity") or "INFO").upper()
            message = str(item.get("message") or item.get("msg") or item.get("error") or str(item))
            raw = json.dumps(item)

            entries.append(LogEntry(
                line_id=line_id,
                timestamp=ts,
                service=service,
                level=level,
                message=message,
                raw=raw
            ))
        return entries

    @classmethod
    def _parse_csv(cls, content: str) -> List[LogEntry]:
        entries: List[LogEntry] = []
        f = io.StringIO(content)
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=1):
            line_id = f"L-{idx:04d}"
            ts_val = row.get("timestamp") or row.get("time") or datetime.utcnow()
            ts = cls._parse_timestamp(ts_val)
            service = str(row.get("service") or row.get("component") or row.get("app") or "unknown-service").strip()
            level = str(row.get("level") or row.get("severity") or "INFO").strip().upper()
            message = str(row.get("message") or row.get("msg") or row.get("description") or "").strip()
            raw = ",".join(f"{k}:{v}" for k, v in row.items())

            entries.append(LogEntry(
                line_id=line_id,
                timestamp=ts,
                service=service,
                level=level,
                message=message,
                raw=raw
            ))
        return entries

    @classmethod
    def _parse_txt(cls, content: str) -> List[LogEntry]:
        entries: List[LogEntry] = []
        lines = content.splitlines()
        for idx, line in enumerate(lines, start=1):
            line_str = line.strip()
            if not line_str:
                continue
            line_id = f"L-{idx:04d}"
            m = cls.LOG_LINE_REGEX.match(line_str)
            if m:
                ts = cls._parse_timestamp(m.group("timestamp"))
                service = m.group("service").strip("[] ")
                level = m.group("level").strip("[] ").upper()
                msg = m.group("message").strip()
            else:
                # Fallback splitting
                parts = line_str.split(maxsplit=3)
                if len(parts) >= 4:
                    ts = cls._parse_timestamp(f"{parts[0]} {parts[1]}")
                    service = parts[2].strip("[]:")
                    level = "INFO"
                    msg = parts[3]
                else:
                    ts = datetime.utcnow()
                    service = "app"
                    level = "INFO"
                    msg = line_str

            entries.append(LogEntry(
                line_id=line_id,
                timestamp=ts,
                service=service,
                level=level,
                message=msg,
                raw=line_str
            ))
        return entries

