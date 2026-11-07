import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from config import AUDIT_LOG_PATH, REPORTS_DIR
from core.schemas import IncidentReport, IncidentMemoryEntry
from guardrails.input_guard import InputGuard
from guardrails.output_guard import OutputGuard
from processing.parser import LogParser
from processing.templates import TemplateMiner
from processing.detector import ErrorDetector
from reasoning.causal_graph import CausalPropagationGraph
from reasoning.hypothesis import HypothesisAgent
from reasoning.verifier import AdversarialVerifier
from decision.severity import HybridSeverityCalculator
from decision.report import ReportGenerator
from knowledge_base.rag import KnowledgeBaseRAG

class PipelineOrchestrator:
    """Executes the complete IncidentX L1 through L7 investigation pipeline."""

    def __init__(self):
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    def log_audit(self, layer: str, action: str, status: str, details: Dict[str, Any]):
        """Appends structured JSON entry to outputs/audit.log."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "layer": layer,
            "action": action,
            "status": status,
            "details": details
        }
        try:
            with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except Exception as e:
            print(f"[Audit] Failed to append to audit log: {e}")

    def run_investigation(
        self,
        raw_log_content: str,
        scenario_name: Optional[str] = None,
        file_format: Optional[str] = None
    ) -> IncidentReport:
        incident_id = f"INC-{uuid.uuid4().hex[:6].upper()}"

        # -------------------------------------------------------------
        # L1: INPUT GUARDRAILS
        # -------------------------------------------------------------
        input_guard_res = InputGuard.process_text(raw_log_content)
        self.log_audit(
            layer="L1_INPUT_GUARDRAILS",
            action="sanitize_and_scan",
            status="BLOCKED" if not input_guard_res.passed else "PASS",
            details={
                "pii_redacted": input_guard_res.pii_redaction_count,
                "injection_detected": input_guard_res.injection_detected,
                "quarantined_count": len(input_guard_res.quarantined_lines),
                "violations": input_guard_res.violations
            }
        )

        sanitized_content = input_guard_res.sanitized_content

        # -------------------------------------------------------------
        # L2: LOG PROCESSING (Normalization & Templates)
        # -------------------------------------------------------------
        entries = LogParser.parse_content(sanitized_content, file_type=file_format)
        templates = TemplateMiner.mine(entries, max_templates=25)
        valid_line_ids = {e.line_id for e in entries}

        self.log_audit(
            layer="L2_LOG_PROCESSING",
            action="parse_and_mine_templates",
            status="PASS",
            details={
                "total_entries": len(entries),
                "unique_templates_mined": len(templates)
            }
        )

        # -------------------------------------------------------------
        # L3: ERROR DETECTION (Windowed Anomaly & Onset Detection)
        # -------------------------------------------------------------
        anomalies = ErrorDetector.detect_anomalies(entries)
        self.log_audit(
            layer="L3_ERROR_DETECTION",
            action="detect_anomalies_and_onsets",
            status="PASS",
            details={
                "anomalous_services_count": len(anomalies),
                "services": [a.service for a in anomalies]
            }
        )

        # -------------------------------------------------------------
        # L4: REASONING CORE
        # Innovation 1: Auto-inferred Causal Propagation Graph
        # Innovation 2: Hypothesis Tournament with Adversarial Verifier
        # -------------------------------------------------------------
        causal_graph = CausalPropagationGraph.build(anomalies, entries)
        self.log_audit(
            layer="L4_REASONING_INNOVATION_1",
            action="infer_causal_graph",
            status="PASS",
            details={
                "ranked_root_candidates": causal_graph.ranked_root_candidates,
                "edges_count": len(causal_graph.edges)
            }
        )

        hypotheses = HypothesisAgent.generate_hypotheses(causal_graph, anomalies, entries)
        tournament_result = AdversarialVerifier.run_tournament(hypotheses, causal_graph, entries)
        
        self.log_audit(
            layer="L4_REASONING_INNOVATION_2",
            action="hypothesis_tournament",
            status="PASS",
            details={
                "hypotheses_evaluated": len(hypotheses),
                "winning_hypothesis": tournament_result.winning_hypothesis.title if tournament_result.winning_hypothesis else None,
                "confidence": tournament_result.confidence
            }
        )

        root_service = (
            tournament_result.winning_hypothesis.root_service 
            if tournament_result.winning_hypothesis 
            else (causal_graph.ranked_root_candidates[0] if causal_graph.ranked_root_candidates else "unknown")
        )

        # -------------------------------------------------------------
        # L5: DECISION LAYER (Hybrid Severity + RAG Knowledge Base)
        # -------------------------------------------------------------
        severity_result = HybridSeverityCalculator.calculate(anomalies, causal_graph)
        
        # Search RAG runbooks and past incidents
        query = f"{root_service} " + " ".join([a.error_category for a in anomalies])
        matched_runbooks = KnowledgeBaseRAG.search_runbooks(query, top_k=1)
        matched_runbook = matched_runbooks[0][0] if matched_runbooks else None
        
        similar_past = KnowledgeBaseRAG.search_incident_memory(query, top_k=2)
        past_incidents_data = [
            {
                "incident_id": inc.incident_id,
                "title": inc.title,
                "root_cause_service": inc.root_cause_service,
                "root_cause_description": inc.root_cause_description,
                "resolution_summary": inc.resolution_summary,
                "similarity": sim
            }
            for inc, sim in similar_past
        ]

        self.log_audit(
            layer="L5_DECISION",
            action="severity_and_rag_lookup",
            status="PASS",
            details={
                "base_severity": severity_result.base_severity.value,
                "final_severity": severity_result.final_severity.value,
                "matched_runbook": matched_runbook.id if matched_runbook else None,
                "similar_incidents_count": len(past_incidents_data)
            }
        )

        # Collect all cited line IDs
        all_citations = set()
        for h in tournament_result.hypotheses:
            all_citations.update(h.confirming_citations)
            all_citations.update(h.refuting_citations)
        for a in anomalies:
            all_citations.update(a.sample_line_ids)

        # -------------------------------------------------------------
        # L6: OUTPUT GUARDRAILS + REPORT GENERATION
        # -------------------------------------------------------------
        report = ReportGenerator.generate(
            incident_id=incident_id,
            scenario_name=scenario_name,
            severity=severity_result,
            root_cause_service=root_service,
            tournament=tournament_result,
            causal_graph=causal_graph,
            runbook=matched_runbook,
            similar_incidents=past_incidents_data,
            entries=entries,
            all_citations=sorted(list(all_citations))
        )

        output_guard_res = OutputGuard.validate_report(
            report_markdown=report.markdown_report,
            valid_line_ids=valid_line_ids,
            severity_value=report.severity.final_severity.value,
            confidence_score=tournament_result.confidence,
            has_runbook=(matched_runbook is not None)
        )

        report.markdown_report = output_guard_res.sanitized_report
        report.requires_human_approval = output_guard_res.requires_human_review

        self.log_audit(
            layer="L6_OUTPUT_GUARDRAILS",
            action="validate_citations_and_grounding",
            status="PASS" if output_guard_res.passed else "WARN",
            details={
                "valid_citations_count": len(output_guard_res.valid_citations),
                "hallucinated_citations": output_guard_res.hallucinated_citations,
                "violations": output_guard_res.violations
            }
        )

        # Persist report to file
        report_file = REPORTS_DIR / f"{incident_id}.md"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report.markdown_report)

        return report

    def approve_remediation(self, report: IncidentReport) -> bool:
        """L7 Governance: Human-in-the-loop approval step that triggers resolution and updates incident memory."""
        report.approved_by_human = True
        report.requires_human_approval = False

        # Persist to incident memory so system learns
        new_memory = IncidentMemoryEntry(
            incident_id=report.incident_id,
            title=f"Incident in {report.root_cause_service} ({report.scenario_name or 'Production'})",
            root_cause_service=report.root_cause_service,
            root_cause_description=report.summary,
            severity=report.severity.final_severity.value,
            resolution_summary=(
                f"Approved remediation from Runbook {report.retrieved_runbook.id if report.retrieved_runbook else 'N/A'}: "
                f"{'; '.join(report.remediation_plan[:2])}"
            ),
            citations=report.evidence_citations[:4]
        )
        KnowledgeBaseRAG.save_incident_memory(new_memory)

        self.log_audit(
            layer="L7_GOVERNANCE",
            action="approve_remediation_and_learn",
            status="EXECUTED",
            details={
                "incident_id": report.incident_id,
                "approved": True,
                "memory_updated": True
            }
        )
        return True

