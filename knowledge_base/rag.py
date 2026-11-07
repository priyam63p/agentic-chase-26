import json
import math
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
from core.schemas import Runbook, IncidentMemoryEntry
from core.llm import llm_client
from config import RUNBOOKS_PATH, INCIDENT_MEMORY_PATH

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    n1 = math.sqrt(sum(a * a for a in v1))
    n2 = math.sqrt(sum(b * b for b in v2))
    if n1 == 0 or n2 == 0:
        return 0.0
    return float(dot / (n1 * n2))

class KnowledgeBaseRAG:
    """RAG engine for production runbooks and historical incident memory."""

    @classmethod
    def load_runbooks(cls) -> List[Runbook]:
        if not RUNBOOKS_PATH.exists():
            return []
        try:
            with open(RUNBOOKS_PATH, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            return [Runbook(**item) for item in data]
        except Exception as e:
            print(f"[RAG] Error loading runbooks: {e}")
            return []

    @classmethod
    def load_incident_memory(cls) -> List[IncidentMemoryEntry]:
        if not INCIDENT_MEMORY_PATH.exists():
            return []
        try:
            with open(INCIDENT_MEMORY_PATH, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            return [IncidentMemoryEntry(**item) for item in data]
        except Exception as e:
            print(f"[RAG] Error loading incident memory: {e}")
            return []

    @classmethod
    def save_incident_memory(cls, entry: IncidentMemoryEntry):
        current = cls.load_incident_memory()
        # Avoid duplicate IDs
        current = [e for e in current if e.incident_id != entry.incident_id]
        current.append(entry)
        try:
            with open(INCIDENT_MEMORY_PATH, "w", encoding="utf-8") as f:
                json.dump([e.model_dump(mode="json") for e in current], f, indent=2, default=str)
        except Exception as e:
            print(f"[RAG] Error saving incident memory: {e}")

    @classmethod
    def search_runbooks(cls, query: str, top_k: int = 3, threshold: float = 0.2) -> List[Tuple[Runbook, float]]:
        runbooks = cls.load_runbooks()
        if not runbooks:
            return []

        # Prepare corpus texts
        corpus = [
            f"{rb.title} {rb.category} {' '.join(rb.keywords)} {' '.join(rb.symptoms)}"
            for rb in runbooks
        ]
        q_emb = llm_client.embed([query])[0]
        c_embs = llm_client.embed(corpus)

        results = []
        for rb, c_emb in zip(runbooks, c_embs):
            sim = cosine_similarity(q_emb, c_emb)
            # Add keyword match boost
            q_words = set(query.lower().split())
            kw_match = sum(1 for kw in rb.keywords if kw.lower() in query.lower() or any(w in kw.lower() for w in q_words))
            score = sim + (0.15 * min(kw_match, 3))
            if score >= threshold:
                results.append((rb, round(score, 4)))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    @classmethod
    def search_incident_memory(cls, query: str, top_k: int = 3, threshold: float = 0.2) -> List[Tuple[IncidentMemoryEntry, float]]:
        incidents = cls.load_incident_memory()
        if not incidents:
            return []

        corpus = [
            f"{inc.incident_id} {inc.title} {inc.root_cause_service} {inc.root_cause_description} {inc.resolution_summary}"
            for inc in incidents
        ]
        q_emb = llm_client.embed([query])[0]
        c_embs = llm_client.embed(corpus)

        results = []
        for inc, c_emb in zip(incidents, c_embs):
            sim = cosine_similarity(q_emb, c_emb)
            if query.lower() in inc.root_cause_service.lower() or inc.root_cause_service.lower() in query.lower():
                sim += 0.25
            if sim >= threshold:
                results.append((inc, round(sim, 4)))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

