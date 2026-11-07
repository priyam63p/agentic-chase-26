import json
from typing import List, Dict, Any, Optional
from core.schemas import SeverityLevel, SeverityResult, Anomaly, CausalGraphResult
from core.llm import llm_client
from config import SEVERITY_WEIGHTS, SEVERITY_BANDS, CRITICAL_SERVICES, USER_FACING_SERVICES

class HybridSeverityCalculator:
    """Calculates defensible 4-factor weighted severity with bounded LLM +/- 1 level adjustment."""

    SEVERITY_ORDER = [SeverityLevel.LOW, SeverityLevel.MEDIUM, SeverityLevel.HIGH, SeverityLevel.CRITICAL]

    @classmethod
    def calculate(
        cls,
        anomalies: List[Anomaly],
        causal_graph: CausalGraphResult,
        user_facing_override: Optional[bool] = None
    ) -> SeverityResult:
        if not anomalies:
            return SeverityResult(
                availability_score=0.1,
                blast_radius_score=0.1,
                error_rate_score=0.1,
                user_facing_score=0.1,
                base_score=0.1,
                base_severity=SeverityLevel.LOW,
                llm_adjustment=0,
                final_severity=SeverityLevel.LOW,
                justification="No operational anomalies detected."
            )

        affected_services = [a.service for a in anomalies]
        peak_err = max(a.peak_error_rate for a in anomalies)
        
        # 1. Availability Impact (35%)
        # Check if any service experienced crash, OOM, or complete downtime
        has_fatal = any(
            a.error_category in ("MEMORY_LEAK_OOM", "DISK_EXHAUSTION", "BAD_DEPLOYMENT") 
            or a.peak_error_rate > 0.8 
            for a in anomalies
        )
        if has_fatal:
            avail_score = 1.0
        elif peak_err > 0.4:
            avail_score = 0.75
        elif peak_err > 0.15:
            avail_score = 0.50
        else:
            avail_score = 0.25

        # 2. Blast Radius (25%)
        # Ratio of affected services and criticality
        crit_count = sum(1 for s in affected_services if any(c in s.lower() for c in CRITICAL_SERVICES))
        base_radius = min(1.0, len(affected_services) / 4.0)
        blast_score = min(1.0, base_radius + (0.2 * crit_count))

        # 3. Error Rate & Trend (20%)
        # Higher error rate -> higher severity
        err_trend_score = min(1.0, peak_err * 1.2)

        # 4. User-Facing Impact (20%)
        if user_facing_override is not None:
            user_score = 1.0 if user_facing_override else 0.3
        else:
            has_user_facing = any(
                any(u in s.lower() for u in USER_FACING_SERVICES) for s in affected_services
            )
            user_score = 1.0 if has_user_facing else 0.35

        # Composite Weighted Score
        base_score = (
            SEVERITY_WEIGHTS["availability_impact"] * avail_score +
            SEVERITY_WEIGHTS["blast_radius"] * blast_score +
            SEVERITY_WEIGHTS["error_rate_trend"] * err_trend_score +
            SEVERITY_WEIGHTS["user_facing"] * user_score
        )
        base_score = round(base_score, 3)

        # Map to band
        base_sev = SeverityLevel.LOW
        for low, high, label in SEVERITY_BANDS:
            if low <= base_score < high:
                base_sev = SeverityLevel(label)
                break
        if base_score >= 0.75:
            base_sev = SeverityLevel.CRITICAL

        # LLM +/- 1 adjustment
        adjustment = 0
        justification = (
            f"Deterministic formula calculated score {base_score:.3f} ({base_sev.value}) based on: "
            f"Availability={avail_score:.2f} (35%), Blast Radius={blast_score:.2f} (25%), "
            f"Error Rate={err_trend_score:.2f} (20%), User-Facing={user_score:.2f} (20%)."
        )

        if llm_client.is_live():
            try:
                prompt = (
                    f"Incident metrics:\n"
                    f"- Base Score: {base_score:.2f} -> Base Severity: {base_sev.value}\n"
                    f"- Affected services: {affected_services}\n"
                    f"- Peak error rate: {peak_err:.2%}\n"
                    f"You may adjust severity by at most +/- 1 level (-1, 0, +1). "
                    f"Provide response JSON: {{\"adjustment\": -1|0|1, \"reason\": \"...\"}}"
                )
                raw = llm_client.generate(prompt=prompt)
                parsed = json.loads(raw)
                adj = int(parsed.get("adjustment", 0))
                # Strictly bound to -1, 0, +1
                adj = max(-1, min(1, adj))
                adjustment = adj
                justification += f" LLM adjustment ({adjustment:+d}): {parsed.get('reason', '')}"
            except Exception:
                pass

        # Apply bounded adjustment
        base_idx = cls.SEVERITY_ORDER.index(base_sev)
        final_idx = max(0, min(len(cls.SEVERITY_ORDER) - 1, base_idx + adjustment))
        final_sev = cls.SEVERITY_ORDER[final_idx]

        return SeverityResult(
            availability_score=round(avail_score, 2),
            blast_radius_score=round(blast_score, 2),
            error_rate_score=round(err_trend_score, 2),
            user_facing_score=round(user_score, 2),
            base_score=base_score,
            base_severity=base_sev,
            llm_adjustment=adjustment,
            final_severity=final_sev,
            justification=justification
        )
