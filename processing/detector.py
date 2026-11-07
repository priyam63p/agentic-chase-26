import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
import numpy as np
from core.schemas import LogEntry, Anomaly, TimeWindow
from config import DEFAULT_WINDOW_SECONDS, ANOMALY_RATIO_THRESHOLD, ZSCORE_THRESHOLD

class ErrorDetector:
    """Detects time-windowed error spikes, computes anomaly onset times per service, and classifies anomaly types."""

    ERROR_LEVELS = {"ERROR", "CRITICAL", "FATAL"}
    
    ERROR_KEYWORDS = re.compile(
        r'(?i)(exception|fail|timeout|refused|error|crash|out of memory|oom|kill|disk full|no space|exhausted|5\d{2})'
    )

    CATEGORY_PATTERNS = [
        ("DATABASE_FAILURE", re.compile(r'(?i)(database|db|postgres|mysql|connection pool|pool exhausted|query timeout|deadlock)')),
        ("MEMORY_LEAK_OOM", re.compile(r'(?i)(out of memory|oom|heap|garbage collection|gc overhead|memory leak|heap dump)')),
        ("BAD_DEPLOYMENT", re.compile(r'(?i)(deploy|version|release|migration|v\d+\.\d+|rollback|startup failure)')),
        ("DISK_EXHAUSTION", re.compile(r'(?i)(disk full|no space left on device|filesystem|inode|write failed)')),
        ("CACHE_WARNING", re.compile(r'(?i)(cache|redis|memcached|eviction|ttl expired|stale cache)')),
        ("NETWORK_TIMEOUT", re.compile(r'(?i)(connection refused|upstream timeout|gateway timeout|connection reset|handshake)'))
    ]

    @classmethod
    def is_error_entry(cls, entry: LogEntry) -> bool:
        if entry.level in cls.ERROR_LEVELS:
            return True
        if cls.ERROR_KEYWORDS.search(entry.message):
            return True
        return False

    @classmethod
    def classify_category(cls, messages: List[str]) -> str:
        combined = " ".join(messages)
        for cat, pattern in cls.CATEGORY_PATTERNS:
            if pattern.search(combined):
                return cat
        return "SERVICE_ERROR"

    @classmethod
    def detect_anomalies(cls, entries: List[LogEntry], window_seconds: int = DEFAULT_WINDOW_SECONDS) -> List[Anomaly]:
        if not entries:
            return []

        # Sort entries chronologically
        sorted_entries = sorted(entries, key=lambda e: e.timestamp)
        start_time = sorted_entries[0].timestamp
        end_time = sorted_entries[-1].timestamp
        duration = (end_time - start_time).total_seconds()

        # If time duration is extremely short (e.g. simulated logs under 1 minute), adjust window size
        eff_window = max(5, int(window_seconds))
        if duration > 0 and duration < eff_window * 2:
            eff_window = max(5, int(duration / 4))

        # Group by service
        services: Dict[str, List[LogEntry]] = {}
        for entry in sorted_entries:
            services.setdefault(entry.service, []).append(entry)

        anomalies: List[Anomaly] = []

        for service, s_entries in services.items():
            # Build time windows
            cur_window_start = start_time
            windows: List[TimeWindow] = []
            
            # Map entries to windows
            while cur_window_start <= end_time:
                cur_window_end = cur_window_start + timedelta(seconds=eff_window)
                w_entries = [e for e in s_entries if cur_window_start <= e.timestamp < cur_window_end]
                tot = len(w_entries)
                errs = sum(1 for e in w_entries if cls.is_error_entry(e))
                rate = (errs / tot) if tot > 0 else 0.0
                windows.append(TimeWindow(
                    window_start=cur_window_start,
                    window_end=cur_window_end,
                    service=service,
                    total_count=tot,
                    error_count=errs,
                    error_rate=rate
                ))
                cur_window_start = cur_window_end

            rates = [w.error_rate for w in windows if w.total_count > 0]
            if not rates:
                continue

            mean_rate = float(np.mean(rates))
            std_rate = float(np.std(rates)) if len(rates) > 1 else 0.0

            # Find anomalous windows
            anomalous_windows = []
            for w in windows:
                if w.error_count == 0:
                    continue
                is_anom = False
                # Trigger on ratio threshold or z-score
                if w.error_rate >= ANOMALY_RATIO_THRESHOLD:
                    is_anom = True
                elif std_rate > 0.001 and ((w.error_rate - mean_rate) / std_rate) >= ZSCORE_THRESHOLD:
                    is_anom = True
                elif mean_rate == 0.0 and w.error_count > 0:
                    is_anom = True

                if is_anom:
                    anomalous_windows.append(w)

            if anomalous_windows:
                # First anomalous window onset
                first_window = anomalous_windows[0]
                # Determine precise onset time (timestamp of first error in that window)
                window_errors = [
                    e for e in s_entries 
                    if first_window.window_start <= e.timestamp < first_window.window_end and cls.is_error_entry(e)
                ]
                onset = window_errors[0].timestamp if window_errors else first_window.window_start

                peak_rate = max(w.error_rate for w in anomalous_windows)
                total_err_count = sum(w.error_count for w in anomalous_windows)
                total_window_count = sum(w.total_count for w in anomalous_windows)

                # Collect sample line IDs and templates
                all_error_entries = [e for e in s_entries if cls.is_error_entry(e)]
                sample_ids = [e.line_id for e in all_error_entries[:5]]
                templates = list(set([e.template for e in all_error_entries if e.template]))
                category = cls.classify_category([e.message for e in all_error_entries])

                anomalies.append(Anomaly(
                    service=service,
                    onset_time=onset,
                    peak_error_rate=round(peak_rate, 4),
                    error_count=total_err_count,
                    total_count=total_window_count,
                    error_category=category,
                    sample_line_ids=sample_ids,
                    affected_templates=templates
                ))

        # Sort anomalies chronologically by onset time
        anomalies.sort(key=lambda a: a.onset_time)
        return anomalies
