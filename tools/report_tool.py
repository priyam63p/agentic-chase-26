from typing import Dict, Any, List

class ReportTool:
    """Tool for structuring and validating report sections."""

    @staticmethod
    def structure_summary(
        title: str,
        root_cause_service: str,
        primary_evidence: List[str],
        impacted_services: List[str]
    ) -> Dict[str, Any]:
        return {
            "title": title,
            "root_cause_service": root_cause_service,
            "primary_evidence": primary_evidence,
            "impacted_services": impacted_services,
            "formatted_summary": (
                f"Incident Investigation determined root cause originating in service `{root_cause_service}`. "
                f"Propagation impacted downstream components: {', '.join(impacted_services)}. "
                f"Primary evidence confirmed at log citations: {', '.join(primary_evidence)}."
            )
        }
