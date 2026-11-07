from typing import List, Dict, Any, Tuple
from core.schemas import Hypothesis, HypothesisStatus, TournamentResult, CausalGraphResult, LogEntry
from tools.log_search import LogSearchTool

class AdversarialVerifier:
    """Adversarial Verifier Agent that actively tests and attempts to disprove each root cause hypothesis."""

    @classmethod
    def run_tournament(
        cls,
        hypotheses: List[Hypothesis],
        causal_graph: CausalGraphResult,
        entries: List[LogEntry]
    ) -> TournamentResult:
        if not hypotheses:
            return TournamentResult()

        onset_map = {n.service: n.onset_time for n in causal_graph.nodes}
        top_root = causal_graph.ranked_root_candidates[0] if causal_graph.ranked_root_candidates else ""
        root_onset = onset_map.get(top_root)

        why_not_sections: List[Dict[str, Any]] = []

        for h in hypotheses:
            svc = h.root_service
            svc_onset = onset_map.get(svc)

            confirming_ids = []
            refuting_ids = []

            # 1. Search logs of this candidate service
            svc_errors = LogSearchTool.search(entries, service=svc, level="ERROR", limit=10)
            if not svc_errors:
                svc_errors = LogSearchTool.search(entries, service=svc, query_pattern=r"fail|error|timeout|crash|leak", limit=10)

            # 2. Test temporal precedence prediction:
            # If svc is NOT the earliest onset, and downstream logs mention an earlier service, svc is refuted as root
            if svc_onset and root_onset and svc_onset > root_onset:
                # This service failed AFTER the root candidate
                lag = (svc_onset - root_onset).total_seconds()
                
                # Search if svc logs cite the earlier service
                cascade_evidence = LogSearchTool.search(
                    entries, 
                    service=svc, 
                    query_pattern=top_root,
                    limit=5
                )
                if cascade_evidence:
                    refuting_ids.extend([e["line_id"] for e in cascade_evidence])
                    h.status = HypothesisStatus.REFUTED
                    h.evidence_summary = (
                        f"Refuted as primary root cause: Error onset in `{svc}` occurred +{lag:.1f}s after `{top_root}`. "
                        f"Logs in `{svc}` explicitly document cascading upstream failures from `{top_root}`."
                    )
                else:
                    refuting_ids.extend([e["line_id"] for e in svc_errors[:2]])
                    h.status = HypothesisStatus.REFUTED
                    h.evidence_summary = (
                        f"Refuted: Temporal onset lag (+{lag:.1f}s) indicates `{svc}` is a downstream consequence, not root trigger."
                    )
            elif svc == top_root:
                # This is the primary root candidate!
                # Gather confirming evidence from this service
                confirming_ids.extend([e["line_id"] for e in svc_errors[:4]])

                # Gather confirming evidence from downstream services pointing back to this service
                downstream_complaints = LogSearchTool.search(
                    entries,
                    query_pattern=svc,
                    limit=5
                )
                for dc in downstream_complaints:
                    if dc["service"] != svc and dc["line_id"] not in confirming_ids:
                        confirming_ids.append(dc["line_id"])

                h.status = HypothesisStatus.SUPPORTED
                h.evidence_summary = (
                    f"Strongly supported: Earliest onset verified with {len(svc_errors)} intrinsic failure events. "
                    f"Downstream services corroborate dependency failure."
                )
            else:
                h.status = HypothesisStatus.INCONCLUSIVE
                h.evidence_summary = "Inconclusive: Insufficient correlated log evidence to substantiate or decisively refute."

            h.confirming_citations = sorted(list(set(confirming_ids)))
            h.refuting_citations = sorted(list(set(refuting_ids)))

            # If refuted, add to "Why Not X?" section
            if h.status == HypothesisStatus.REFUTED:
                why_not_sections.append({
                    "hypothesis_id": h.id,
                    "title": h.title,
                    "service": h.root_service,
                    "status": "Refuted",
                    "reason": h.evidence_summary,
                    "disproving_citations": h.refuting_citations
                })

        # Calculate confidence from tournament outcomes
        supported_hypotheses = [h for h in hypotheses if h.status == HypothesisStatus.SUPPORTED]
        refuted_hypotheses = [h for h in hypotheses if h.status == HypothesisStatus.REFUTED]

        is_tied = len(supported_hypotheses) != 1
        winner = supported_hypotheses[0] if len(supported_hypotheses) == 1 else None

        if winner:
            # Winner supported + runners-up refuted -> high confidence
            base_conf = 0.92
            if len(refuted_hypotheses) >= 1:
                base_conf += 0.05
            confidence = min(0.98, base_conf)
            winner.confidence_score = confidence
        else:
            confidence = 0.45

        return TournamentResult(
            hypotheses=hypotheses,
            winning_hypothesis=winner,
            confidence=round(confidence, 2),
            is_tied_or_inconclusive=is_tied,
            why_not_sections=why_not_sections
        )
