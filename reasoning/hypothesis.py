import json
from typing import List, Dict, Any
from core.schemas import Hypothesis, CausalGraphResult, Anomaly, LogEntry
from core.llm import llm_client
from guardrails.prompt_guard import PromptGuard

class HypothesisAgent:
    """Generates competing root-cause hypotheses seeded by the causal propagation graph."""

    @classmethod
    def generate_hypotheses(
        cls,
        causal_graph: CausalGraphResult,
        anomalies: List[Anomaly],
        entries: List[LogEntry]
    ) -> List[Hypothesis]:
        if not causal_graph.ranked_root_candidates:
            return []

        top_candidates = causal_graph.ranked_root_candidates[:3]
        anom_map = {a.service: a for a in anomalies}

        # If LLM is live, we can prompt it to formulate hypotheses with strict schema
        if llm_client.is_live():
            try:
                prompt = (
                    f"Given anomalous services: {[a.service for a in anomalies]} and causal root candidates {top_candidates},\n"
                    f"propose 2 to 3 distinct competing root cause hypotheses for an adversarial tournament.\n"
                    f"Each hypothesis must specify:\n"
                    f"- id (H1, H2, H3)\n"
                    f"- title\n"
                    f"- description\n"
                    f"- root_service\n"
                    f"- testable_predictions (list of concrete statements to verify in logs)"
                )
                system_prompt = PromptGuard.build_system_prompt(
                    role="Hypothesis Formulation Agent",
                    instructions=[
                        "Propose competing hypotheses for root cause vs symptom disambiguation.",
                        "Include at least one alternative or decoy hypothesis.",
                        "Formulate strict testable predictions regarding temporal precedence and error messages."
                    ]
                )
                raw_resp = llm_client.generate(prompt=prompt, system_instruction=system_prompt)
                # Parse JSON if possible
                parsed = json.loads(raw_resp)
                if isinstance(parsed, list):
                    return [Hypothesis(**h) for h in parsed]
                elif isinstance(parsed, dict) and "hypotheses" in parsed:
                    return [Hypothesis(**h) for h in parsed["hypotheses"]]
            except Exception as e:
                print(f"[HypothesisAgent] LLM formulation fallback: {e}")

        # Deterministic generation seeded by Causal Graph
        hypotheses: List[Hypothesis] = []
        
        # Primary candidate (top of causal graph)
        primary_svc = top_candidates[0]
        primary_anom = anom_map.get(primary_svc)
        p_cat = primary_anom.error_category if primary_anom else "FAILURE"
        
        h1 = Hypothesis(
            id="H1",
            title=f"Primary Root Cause: {p_cat.replace('_', ' ').title()} in `{primary_svc}`",
            description=f"Failure initiated in `{primary_svc}` due to internal fault, propagating downstream to other services.",
            root_service=primary_svc,
            testable_predictions=[
                f"`{primary_svc}` anomaly onset timestamp must strictly precede downstream errors.",
                f"`{primary_svc}` log entries must show intrinsic fatal errors or resource exhaustion.",
                f"Downstream service error logs must reference connection or timeout failures to `{primary_svc}`."
            ]
        )
        hypotheses.append(h1)

        # Secondary candidate (downstream symptom or competitor)
        if len(top_candidates) > 1:
            second_svc = top_candidates[1]
            sec_anom = anom_map.get(second_svc)
            s_cat = sec_anom.error_category if sec_anom else "SERVICE_ERROR"
            
            h2 = Hypothesis(
                id="H2",
                title=f"Alternative Hypothesis: Independent Failure in `{second_svc}`",
                description=f"Failure originated independently in `{second_svc}` ({s_cat}) and was not a mere cascade from `{primary_svc}`.",
                root_service=second_svc,
                testable_predictions=[
                    f"`{second_svc}` errors must begin prior to or independent of `{primary_svc}`.",
                    f"`{second_svc}` error logs should not reference `{primary_svc}` timeouts as trigger.",
                    f"`{second_svc}` must exhibit autonomous internal crash without upstream dependency failure."
                ]
            )
            hypotheses.append(h2)

        # Third candidate if available (e.g. decoy or tertiary)
        if len(top_candidates) > 2:
            third_svc = top_candidates[2]
            h3 = Hypothesis(
                id="H3",
                title=f"Decoy / Concurrent Incident: Transient Fault in `{third_svc}`",
                description=f"`{third_svc}` failure is the true root driver, or is an unrelated noisy background symptom.",
                root_service=third_svc,
                testable_predictions=[
                    f"`{third_svc}` errors must persist and correlate directly with end-user degradation.",
                    f"Mitigating `{third_svc}` would restore end-to-end service availability."
                ]
            )
            hypotheses.append(h3)

        return hypotheses
