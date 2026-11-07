# IncidentX Agents Overview

## Shared Memory
All agents in the IncidentX system communicate through a **shared in‑memory store** implemented as a thread‑safe Python dictionary (`shared_memory: dict`).  Each agent receives a reference to this dictionary at initialization, allowing them to read and write state without persisting to disk.  The store holds keys such as:

- `incident_log` – raw logs being processed
- `hypotheses` – list of generated hypotheses
- `verdict` – final decision (`approved`, `rejected`)
- `feedback` – user approval flag (`True`/`False`)
- `error_report` – details of any detected error that needs fixing

> **Note:** The shared memory is injected by the `PipelineOrchestrator` when it constructs each agent.

## Existing Agents
| Agent | Module | Role |
|-------|--------|------|
| **PipelineOrchestrator** | `core/orchestrator.py` | Coordinates the L1‑L7 pipeline, creates agents, and passes the shared memory.
| **InputGuard** | `guardrails/input_guard.py` | Validates incoming data.
| **OutputGuard** | `guardrails/output_guard.py` | Sanitises final outputs.
| **CausalPropagationGraph** | `reasoning/causal_graph.py` | Builds a causal graph of events.
| **HypothesisAgent** | `reasoning/hypothesis.py` | Generates possible incident hypotheses.
| **AdversarialVerifier** | `reasoning/verifier.py` | Checks hypotheses against evidence.
| **HybridSeverityCalculator** | `decision/severity.py` | Computes severity scores.
| **ReportGenerator** | `decision/report.py` | Produces the human‑readable incident report.

## New Agents (Added)
| Agent | Module | Role |
|-------|--------|------|
| **FeedbackAgent** | `core/feedback_agent.py` | Waits for user feedback (approval/rejection) and writes the result to `shared_memory["feedback"]`.  It can be triggered from the UI via a simple *Approve* / *Reject* button.
| **FixerAgent** | `core/fixer_agent.py` | Listens for `shared_memory["feedback"] == True` and, once approved, consumes `shared_memory["error_report"]` to apply automated fixes (e.g., patch configuration, retry steps).  It updates `shared_memory["fix_status"]`.

## Interaction Flow (text diagram)
```mermaid
flowchart TD
    A[Start: InputGuard] --> B[Orchestrator]
    B --> C[Reasoning (CausalGraph & HypothesisAgent)]
    C --> D[AdversarialVerifier]
    D --> E[Decision (SeverityCalculator & ReportGenerator)]
    E --> F[OutputGuard]
    F --> G[FeedbackAgent]
    G -->|Approved| H[FixerAgent]
    G -->|Rejected| I[Terminate]
    H --> J[Report Updated]
    I --> J
```

The **FeedbackAgent** bridges the decision layer and the **FixerAgent**, enabling a human‑in‑the‑loop approval step before any automated remediation occurs.

---
*The documentation is placed in `AGENTS.md` at the project root and linked from the UI sidebar (add link in `app.py` if desired).*