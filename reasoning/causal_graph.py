import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Set, Tuple
import networkx as nx

from core.schemas import Anomaly, LogEntry, CausalNode, CausalGraphResult
from config import CAUSAL_LAG_WINDOW_SECONDS

class CausalPropagationGraph:
    """Auto-infers service dependency and failure propagation graph from anomaly onset times and log references."""

    @classmethod
    def build(
        cls,
        anomalies: List[Anomaly],
        entries: List[LogEntry],
        lag_window_seconds: int = CAUSAL_LAG_WINDOW_SECONDS,
        explicit_dependencies: Optional[Dict[str, List[str]]] = None
    ) -> CausalGraphResult:
        if not anomalies:
            return CausalGraphResult()

        # Sort anomalies by onset time
        sorted_anoms = sorted(anomalies, key=lambda a: a.onset_time)
        services = [a.service for a in sorted_anoms]
        onset_map = {a.service: a.onset_time for a in sorted_anoms}

        # Index log entries by service
        service_logs: Dict[str, List[LogEntry]] = {}
        for e in entries:
            service_logs.setdefault(e.service, []).append(e)

        G = nx.DiGraph()
        for a in sorted_anoms:
            G.add_node(a.service, onset_time=a.onset_time)

        edges_info = []

        # Connect nodes based on temporal precedence and textual references / causality
        for i, a in enumerate(sorted_anoms):
            service_a = a.service
            time_a = a.onset_time

            for j, b in enumerate(sorted_anoms):
                if i == j:
                    continue
                service_b = b.service
                time_b = b.onset_time

                lag = (time_b - time_a).total_seconds()
                # Must be after or simultaneous within lag window
                if 0 <= lag <= lag_window_seconds:
                    # Check if service B mentions service A
                    b_entries = service_logs.get(service_b, [])
                    ref_evidence = []
                    a_name_clean = service_a.replace("-", "").replace("_", "")
                    
                    for e in b_entries:
                        msg_clean = e.message.lower().replace("-", "").replace("_", "")
                        if a_name_clean.lower() in msg_clean or service_a.lower() in e.message.lower():
                            ref_evidence.append(e.line_id)

                    # Edge criteria: explicit dependency, text reference, or direct temporal cascade
                    is_edge = False
                    if explicit_dependencies and service_b in explicit_dependencies.get(service_a, []):
                        is_edge = True
                    elif len(ref_evidence) > 0:
                        is_edge = True
                    elif i < j and lag > 0:
                        # If no edges exist into b yet, infer cascade from preceding service
                        if G.in_degree(service_b) == 0:
                            is_edge = True

                    if is_edge and not G.has_edge(service_a, service_b):
                        G.add_edge(service_a, service_b, lag_seconds=lag, evidence=ref_evidence)
                        edges_info.append({
                            "from_service": service_a,
                            "to_service": service_b,
                            "lag_seconds": round(lag, 1),
                            "evidence_line_ids": ref_evidence[:3]
                        })

        # Score candidates for root cause
        earliest_time = sorted_anoms[0].onset_time
        latest_time = sorted_anoms[-1].onset_time
        total_span = max(1.0, (latest_time - earliest_time).total_seconds())

        nodes_list: List[CausalNode] = []
        scores: Dict[str, float] = {}

        for a in sorted_anoms:
            s = a.service
            in_deg = G.in_degree(s)
            out_deg = G.out_degree(s)

            # Onset score: earlier is better (1.0 = earliest)
            onset_score = 1.0 - ((a.onset_time - earliest_time).total_seconds() / total_span)
            
            # In-degree penalty: no incoming edges means nothing upstream caused it
            in_deg_score = 1.0 if in_deg == 0 else (1.0 / (1.0 + in_deg))

            # Out-degree / reachability score: how many services does it cascade to?
            try:
                descendants = nx.descendants(G, s)
                reach_count = len(descendants)
            except Exception:
                reach_count = out_deg
            reach_score = reach_count / max(1, len(services) - 1)

            # Combined deterministic root score
            root_score = (0.45 * onset_score) + (0.35 * in_deg_score) + (0.20 * reach_score)
            scores[s] = round(root_score, 4)

        # Rank candidates
        ranked_candidates = sorted(scores.keys(), key=lambda s: scores[s], reverse=True)
        root_service = ranked_candidates[0] if ranked_candidates else (sorted_anoms[0].service if sorted_anoms else "")
        root_onset = onset_map.get(root_service, earliest_time)

        # Blast radius timeline
        blast_timeline = []
        for rank, s in enumerate(sorted_anoms, start=1):
            lag_from_root = max(0.0, (s.onset_time - root_onset).total_seconds())
            node_obj = CausalNode(
                service=s.service,
                onset_time=s.onset_time,
                in_degree=G.in_degree(s.service),
                out_degree=G.out_degree(s.service),
                root_score=scores.get(s.service, 0.0),
                blast_order=rank,
                lag_seconds_from_root=round(lag_from_root, 1)
            )
            nodes_list.append(node_obj)
            blast_timeline.append({
                "service": s.service,
                "onset_time": s.onset_time.isoformat(),
                "lag_from_root_seconds": round(lag_from_root, 1),
                "is_root": (s.service == root_service)
            })

        # Generate Mermaid diagram
        mermaid_lines = ["graph LR"]
        mermaid_lines.append("    classDef root fill:#ff4d4f,stroke:#8c1d1d,stroke-width:3px,color:#fff,font-weight:bold;")
        mermaid_lines.append("    classDef cascade fill:#ffa39e,stroke:#d4380d,stroke-width:1px,color:#000;")
        mermaid_lines.append("    classDef normal fill:#f5f5f5,stroke:#d9d9d9,stroke-width:1px,color:#333;")

        for n in nodes_list:
            cls_name = "root" if n.service == root_service else "cascade"
            mermaid_lines.append(f'    {n.service.replace("-", "_")}["{n.service}\\n(t={n.lag_seconds_from_root}s)"]:::{cls_name}')

        for edge in edges_info:
            src = edge["from_service"].replace("-", "_")
            dst = edge["to_service"].replace("-", "_")
            lag_label = f'+{edge["lag_seconds"]}s'
            mermaid_lines.append(f'    {src} -->|"{lag_label}"| {dst}')

        mermaid_str = "\n".join(mermaid_lines)

        return CausalGraphResult(
            nodes=nodes_list,
            edges=edges_info,
            ranked_root_candidates=ranked_candidates,
            blast_radius_timeline=blast_timeline,
            mermaid_diagram=mermaid_str
        )
