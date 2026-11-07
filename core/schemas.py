from enum import Enum
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field

class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    FATAL = "FATAL"

class SeverityLevel(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"

class HypothesisStatus(str, Enum):
    SUPPORTED = "Supported"
    REFUTED = "Refuted"
    INCONCLUSIVE = "Inconclusive"

class LogEntry(BaseModel):
    line_id: str = Field(description="Stable sequential identifier e.g. L-0001")
    timestamp: datetime
    service: str
    level: str
    message: str
    raw: str
    template: Optional[str] = None

class LogTemplate(BaseModel):
    template_id: str
    pattern: str
    count: int
    sample_line_ids: List[str] = Field(default_factory=list)

class TimeWindow(BaseModel):
    window_start: datetime
    window_end: datetime
    service: str
    total_count: int
    error_count: int
    error_rate: float

class Anomaly(BaseModel):
    service: str
    onset_time: datetime
    peak_error_rate: float
    error_count: int
    total_count: int
    error_category: str = "GENERIC_ERROR"
    sample_line_ids: List[str] = Field(default_factory=list)
    affected_templates: List[str] = Field(default_factory=list)

class CausalNode(BaseModel):
    service: str
    onset_time: datetime
    in_degree: int = 0
    out_degree: int = 0
    root_score: float = 0.0
    blast_order: int = 1
    lag_seconds_from_root: float = 0.0

class CausalGraphResult(BaseModel):
    nodes: List[CausalNode] = Field(default_factory=list)
    edges: List[Dict[str, Any]] = Field(default_factory=list) # [{from_service, to_service, lag_seconds, evidence_line_ids}]
    ranked_root_candidates: List[str] = Field(default_factory=list)
    blast_radius_timeline: List[Dict[str, Any]] = Field(default_factory=list)
    mermaid_diagram: str = ""

class Hypothesis(BaseModel):
    id: str = Field(description="H1, H2, H3...")
    title: str
    description: str
    root_service: str
    testable_predictions: List[str] = Field(default_factory=list)
    status: HypothesisStatus = HypothesisStatus.INCONCLUSIVE
    confirming_citations: List[str] = Field(default_factory=list)
    refuting_citations: List[str] = Field(default_factory=list)
    evidence_summary: str = ""
    confidence_score: float = 0.0

class TournamentResult(BaseModel):
    hypotheses: List[Hypothesis] = Field(default_factory=list)
    winning_hypothesis: Optional[Hypothesis] = None
    confidence: float = 0.0
    is_tied_or_inconclusive: bool = False
    why_not_sections: List[Dict[str, Any]] = Field(default_factory=list)

class SeverityResult(BaseModel):
    availability_score: float
    blast_radius_score: float
    error_rate_score: float
    user_facing_score: float
    base_score: float
    base_severity: SeverityLevel
    llm_adjustment: int = 0 # -1, 0, or +1
    final_severity: SeverityLevel
    justification: str

class Runbook(BaseModel):
    id: str
    title: str
    category: str
    keywords: List[str] = Field(default_factory=list)
    symptoms: List[str] = Field(default_factory=list)
    remediation_steps: List[str] = Field(default_factory=list)
    verification_steps: List[str] = Field(default_factory=list)

class IncidentMemoryEntry(BaseModel):
    incident_id: str
    title: str
    root_cause_service: str
    root_cause_description: str
    severity: str
    resolution_summary: str
    citations: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class AuditEntry(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    layer: str
    action: str
    status: str
    details: Dict[str, Any] = Field(default_factory=dict)

class IncidentReport(BaseModel):
    incident_id: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    scenario_name: Optional[str] = None
    severity: SeverityResult
    root_cause_service: str
    summary: str
    tournament_result: TournamentResult
    causal_graph: CausalGraphResult
    retrieved_runbook: Optional[Runbook] = None
    similar_incidents: List[Dict[str, Any]] = Field(default_factory=list)
    remediation_plan: List[str] = Field(default_factory=list)
    evidence_citations: List[str] = Field(default_factory=list)
    requires_human_approval: bool = True
    approved_by_human: bool = False
    markdown_report: str = ""
