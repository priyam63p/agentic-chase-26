import pytest
from datetime import datetime, timedelta
from core.schemas import LogEntry
from processing.detector import ErrorDetector
from reasoning.causal_graph import CausalPropagationGraph
from reasoning.hypothesis import HypothesisAgent
from reasoning.verifier import AdversarialVerifier

def test_anomaly_detection_and_onsets():
    t0 = datetime(2026, 11, 7, 10, 0, 0)
    entries = [
        LogEntry(line_id="L-0001", timestamp=t0, service="db", level="CRITICAL", message="db connection pool failure", raw="..."),
        LogEntry(line_id="L-0002", timestamp=t0 + timedelta(seconds=5), service="db", level="ERROR", message="pool exhausted", raw="..."),
        LogEntry(line_id="L-0003", timestamp=t0 + timedelta(seconds=20), service="api", level="ERROR", message="upstream db timeout", raw="..."),
        LogEntry(line_id="L-0004", timestamp=t0 + timedelta(seconds=40), service="web", level="ERROR", message="500 internal server error", raw="...")
    ]

    anomalies = ErrorDetector.detect_anomalies(entries, window_seconds=15)
    assert len(anomalies) >= 2
    
    # db onset should precede api onset
    db_anom = next(a for a in anomalies if a.service == "db")
    api_anom = next(a for a in anomalies if a.service == "api")
    assert db_anom.onset_time <= api_anom.onset_time

def test_causal_graph_ranking():
    t0 = datetime(2026, 11, 7, 10, 0, 0)
    entries = [
        LogEntry(line_id="L-0001", timestamp=t0, service="db-primary", level="CRITICAL", message="fatal out of connections", raw="..."),
        LogEntry(line_id="L-0002", timestamp=t0 + timedelta(seconds=15), service="orders-api", level="ERROR", message="upstream db-primary connection timeout", raw="..."),
        LogEntry(line_id="L-0003", timestamp=t0 + timedelta(seconds=30), service="gateway", level="ERROR", message="orders-api timeout", raw="...")
    ]

    anomalies = ErrorDetector.detect_anomalies(entries, window_seconds=15)
    graph = CausalPropagationGraph.build(anomalies, entries)

    assert len(graph.ranked_root_candidates) >= 2
    # db-primary should be ranked #1 root cause
    assert graph.ranked_root_candidates[0] == "db-primary"
    assert "db_primary" in graph.mermaid_diagram

def test_hypothesis_tournament_and_verifier():
    t0 = datetime(2026, 11, 7, 10, 0, 0)
    entries = [
        LogEntry(line_id="L-0001", timestamp=t0, service="db-primary", level="CRITICAL", message="fatal out of connections", raw="..."),
        LogEntry(line_id="L-0002", timestamp=t0 + timedelta(seconds=15), service="orders-api", level="ERROR", message="upstream db-primary connection timeout", raw="...")
    ]

    anomalies = ErrorDetector.detect_anomalies(entries, window_seconds=15)
    graph = CausalPropagationGraph.build(anomalies, entries)
    hypotheses = HypothesisAgent.generate_hypotheses(graph, anomalies, entries)

    tournament = AdversarialVerifier.run_tournament(hypotheses, graph, entries)
    assert tournament.winning_hypothesis is not None
    assert tournament.winning_hypothesis.root_service == "db-primary"
    assert tournament.confidence >= 0.85
