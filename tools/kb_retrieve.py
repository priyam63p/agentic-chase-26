from typing import Dict, Any, List
from knowledge_base.rag import KnowledgeBaseRAG

class KBRetrieveTool:
    """Tool for retrieving verified runbooks and historical incident memories."""

    @staticmethod
    def retrieve(query: str, target: str = "all") -> Dict[str, Any]:
        results: Dict[str, Any] = {
            "query": query,
            "runbooks": [],
            "past_incidents": []
        }

        if target in ("all", "runbooks"):
            matched_rb = KnowledgeBaseRAG.search_runbooks(query, top_k=2)
            results["runbooks"] = [
                {
                    "id": rb.id,
                    "title": rb.title,
                    "category": rb.category,
                    "remediation_steps": rb.remediation_steps,
                    "verification_steps": rb.verification_steps,
                    "similarity": score
                }
                for rb, score in matched_rb
            ]

        if target in ("all", "incidents"):
            matched_inc = KnowledgeBaseRAG.search_incident_memory(query, top_k=2)
            results["past_incidents"] = [
                {
                    "incident_id": inc.incident_id,
                    "title": inc.title,
                    "root_cause_service": inc.root_cause_service,
                    "root_cause_description": inc.root_cause_description,
                    "resolution_summary": inc.resolution_summary,
                    "similarity": score
                }
                for inc, score in matched_inc
            ]

        return results
