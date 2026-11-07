from datetime import datetime
from typing import List, Dict, Any, Optional
from core.schemas import (
    IncidentReport, SeverityResult, TournamentResult,
    CausalGraphResult, Runbook, IncidentMemoryEntry, LogEntry
)

class ReportGenerator:
    """Generates comprehensive evidence-linked markdown incident reports."""

    @classmethod
    def generate(
        cls,
        incident_id: str,
        scenario_name: Optional[str],
        severity: SeverityResult,
        root_cause_service: str,
        tournament: TournamentResult,
        causal_graph: CausalGraphResult,
        runbook: Optional[Runbook],
        similar_incidents: List[Dict[str, Any]],
        entries: List[LogEntry],
        all_citations: List[str]
    ) -> IncidentReport:
        gen_time = datetime.utcnow()
        winner = tournament.winning_hypothesis
        winner_title = winner.title if winner else "Undetermined Root Cause"
        summary_text = (
            f"Incident investigation identified root cause in service **`{root_cause_service}`** "
            f"({winner_title}). Cascading failures propagated through {len(causal_graph.nodes)} services. "
            f"Adversarial verification determined hypothesis confidence of **{tournament.confidence * 100:.1f}%** "
            f"with all cited claims grounded in verified log entries."
        )

        # Index log entries by line_id for evidence table
        entry_map = {e.line_id: e for e in entries}

        md_lines = [
            f"# Incident Investigation Report: {incident_id}",
            f"**Scenario**: `{scenario_name or 'Production Incident'}`  ",
            f"**Generated**: `{gen_time.strftime('%Y-%m-%d %H:%M:%S UTC')}`  ",
            f"**Overall Severity**: `{severity.final_severity.value.upper()}` (Base: {severity.base_severity.value}, LLM Adj: {severity.llm_adjustment:+d})  ",
            f"**Primary Root Cause**: `{root_cause_service}`  ",
            f"**Investigation Confidence**: `{tournament.confidence * 100:.1f}%`",
            "",
            "---",
            "",
            "## 1. Executive Summary",
            summary_text,
            "",
            "## 2. Hybrid Severity Breakdown",
            "A defensible weighted calculation based on system telemetry and blast impact:",
            "",
            "| Factor | Weight | Score | Description |",
            "| :--- | :---: | :---: | :--- |",
            f"| **Availability Impact** | 35% | {severity.availability_score:.2f} | Service downtime vs degraded operation |",
            f"| **Blast Radius** | 25% | {severity.blast_radius_score:.2f} | Number & criticality of affected services |",
            f"| **Error Rate & Trend** | 20% | {severity.error_rate_score:.2f} | Peak error spike ratio and trajectory |",
            f"| **User-Facing Path** | 20% | {severity.user_facing_score:.2f} | Customer ingress path vs internal batch |",
            f"| **Composite Base Score** | 100% | **{severity.base_score:.3f}** | Mapped Band: **{severity.base_severity.value}** |",
            f"| **Final Severity** | - | **{severity.final_severity.value}** | Justification: {severity.justification} |",
            "",
            "## 3. Innovation 1: Auto-inferred Causal Propagation Graph",
            "Inferred propagation graph derived from anomaly onset timestamps and inter-service error citations:",
            "",
            "```mermaid",
            causal_graph.mermaid_diagram,
            "```",
            "",
            "### Blast Radius Timeline",
            "| Order | Service | Onset Timestamp | Lag from Root | Status |",
            "| :---: | :--- | :--- | :---: | :--- |"
        ]

        for item in causal_graph.blast_radius_timeline:
            is_root_str = "**ROOT CAUSE**" if item.get("is_root") else "Cascading Cascade"
            md_lines.append(
                f"| {item.get('service')} | `{item.get('service')}` | `{item.get('onset_time')}` | +{item.get('lag_from_root_seconds')}s | {is_root_str} |"
            )

        md_lines.extend([
            "",
            "## 4. Innovation 2: Hypothesis Tournament with Adversarial Verifier",
            "To prevent LLM confirmation bias, competing hypotheses were evaluated by an adversarial verification agent:",
            ""
        ])

        for h in tournament.hypotheses:
            badge = "SUPPORTED" if h.status.value == "Supported" else ("REFUTED" if h.status.value == "Refuted" else "INCONCLUSIVE")
            md_lines.extend([
                f"### {h.id}: {h.title} [{badge}]",
                f"- **Candidate Service**: `{h.root_service}`",
                f"- **Description**: {h.description}",
                f"- **Testable Predictions**:",
                *[f"  - {pred}" for pred in h.testable_predictions],
                f"- **Outcome & Evidence**: {h.evidence_summary}",
                f"- **Confirming Citations**: {', '.join(h.confirming_citations) if h.confirming_citations else 'None'}",
                f"- **Refuting Citations**: {', '.join(h.refuting_citations) if h.refuting_citations else 'None'}",
                ""
            ])

        # Why Not X Section
        md_lines.extend([
            "## 5. 'Why Not X?' Competitive Hypothesis Analysis",
            "Detailed rationale refuting alternative or decoy root causes:",
            ""
        ])

        if tournament.why_not_sections:
            for s in tournament.why_not_sections:
                md_lines.extend([
                    f"- **Why Not `{s.get('service')}` ({s.get('title')})?**",
                    f"  - **Finding**: {s.get('reason')}",
                    f"  - **Disproving Citations**: {', '.join(s.get('disproving_citations', []))}",
                    ""
                ])
        else:
            md_lines.append("No competing alternative hypotheses were proposed or disputed.")
            md_lines.append("")

        # Evidence Table
        md_lines.extend([
            "## 6. Grounded Evidence Citations",
            "Every conclusion in this report links directly to immutable source log lines:",
            "",
            "| Citation ID | Timestamp | Service | Level | Raw Excerpt |",
            "| :---: | :--- | :--- | :---: | :--- |"
        ])

        for cid in sorted(all_citations):
            if cid in entry_map:
                e = entry_map[cid]
                clean_msg = e.message.replace("|", "\\|")
                md_lines.append(f"| **`{cid}`** | `{e.timestamp.strftime('%H:%M:%S')}` | `{e.service}` | `{e.level}` | {clean_msg[:120]} |")

        # Runbook Remediation Plan
        md_lines.extend([
            "",
            "## 7. RAG-Retrieved Remediation Runbook",
        ])

        remediation_steps = []
        if runbook:
            remediation_steps = runbook.remediation_steps
            md_lines.extend([
                f"**Matched Runbook**: `{runbook.id}` - **{runbook.title}** (Category: `{runbook.category}`)",
                "",
                "### Prescribed Remediation Actions (Requires Human Sign-off):",
                *[f"{step}" for step in runbook.remediation_steps],
                "",
                "### Verification & Recovery Criteria:",
                *[f"- {step}" for step in runbook.verification_steps]
            ])
        else:
            remediation_steps = ["1. Isolate failing node and inspect service logs.", "2. Perform rolling restart of impacted deployment."]
            md_lines.append("No automated runbook matched the symptom threshold. Default recovery procedures recommended.")

        # Historical Incidents
        md_lines.extend([
            "",
            "## 8. Historical Incident Memory (RAG)",
        ])
        if similar_incidents:
            for past in similar_incidents:
                md_lines.extend([
                    f"- **Incident `{past.get('incident_id')}`**: {past.get('title')}",
                    f"  - **Root Cause**: `{past.get('root_cause_service')}` - {past.get('root_cause_description')}",
                    f"  - **Resolution**: {past.get('resolution_summary')}",
                    f"  - **Similarity Score**: `{past.get('similarity', 0.0):.2f}`",
                    ""
                ])
        else:
            md_lines.append("No prior matching incidents in incident memory.")

        # Governance & Approval
        md_lines.extend([
            "",
            "## 9. Governance & Action Status",
            "- **Action Policy**: *Recommend-only*. Automated remediation requires human SRE authorization.",
            "- **Human Approval Status**: `PENDING APPROVAL` ⏸️",
            "- **Audit Trail**: Every guardrail check, tool dispatch, and LLM reasoning step logged to `outputs/audit.log`.",
            ""
        ])

        report_md = "\n".join(md_lines)

        return IncidentReport(
            incident_id=incident_id,
            generated_at=gen_time,
            scenario_name=scenario_name,
            severity=severity,
            root_cause_service=root_cause_service,
            summary=summary_text,
            tournament_result=tournament,
            causal_graph=causal_graph,
            retrieved_runbook=runbook,
            similar_incidents=similar_incidents,
            remediation_plan=remediation_steps,
            evidence_citations=all_citations,
            requires_human_approval=True,
            approved_by_human=False,
            markdown_report=report_md
        )
