# 🚨 IncidentX: Autonomous Incident Root-Cause Investigation System

> **Design Principle:** *Deterministic code does the measuring. LLMs do the reasoning. Guardrails sit at every boundary. Every conclusion must trace back to specific log lines.*

IncidentX is an industry-grade, autonomous log investigation and root-cause analysis (RCA) platform engineered to diagnose distributed system incidents with mathematical precision, zero hallucinations, and adversarial rigor.

---

## 🌟 Key Architecture & Innovations

IncidentX features a strict **7-Layer Diagnostic Pipeline** powered by two primary innovations:

```
┌──────────────────────────────────────────────────────────────┐
│ L1  INPUT GUARDRAILS                                         │
│     File/size checks · PII redaction · Injection scan        │
└──────────────────────────┬───────────────────────────────────┘
┌──────────────────────────▼───────────────────────────────────┐
│ L2  LOG PROCESSING (Deterministic Code)                      │
│     TXT/JSON/CSV parse → stable IDs (L-0001…) → Template mine│
└──────────────────────────┬───────────────────────────────────┘
┌──────────────────────────▼───────────────────────────────────┐
│ L3  ERROR DETECTION (Rules + Windowing)                      │
│     Windowed error-rate spike detection · Onset time per svc │
└──────────────────────────┬───────────────────────────────────┘
┌──────────────────────────▼───────────────────────────────────┐
│ L4  REASONING CORE                                           │
│     ★ Innovation 1: Auto-inferred Causal Propagation Graph   │
│     ★ Innovation 2: Hypothesis Tournament with Skeptic Agent │
│     Guarded Tools: log_search · error_classifier · kb_retrieve│
└──────────────────────────┬───────────────────────────────────┘
┌──────────────────────────▼───────────────────────────────────┐
│ L5  DECISION LAYER                                           │
│     Hybrid 4-factor severity scoring · RAG runbook & memory  │
└──────────────────────────┬───────────────────────────────────┘
┌──────────────────────────▼───────────────────────────────────┐
│ L6  OUTPUT GUARDRAILS + REPORT                               │
│     Pydantic schema · Citation validation · PII scrub        │
└──────────────────────────┬───────────────────────────────────┘
┌──────────────────────────▼───────────────────────────────────┐
│ L7  GOVERNANCE & UI                                          │
│     Streamlit dashboard · Human approval gate · Audit trail  │
└──────────────────────────────────────────────────────────────┘
```

### 1. Innovation 1: Auto-Inferred Causal Propagation Graph
- **The Problem:** Teams usually require a handwritten, fragile service dependency map. LLMs commonly blame the loudest or last symptom.
- **How IncidentX Solves It:** Takes anomaly onset times $T_0(S)$ from L3 and builds a directed propagation graph $A \to B$ based on temporal onset lag and cross-service error references.
- **Deterministic Root-Cause Scoring:** Scores nodes using:
  - Earliest onset timestamp bonus
  - Zero incoming edges bonus (nothing upstream triggered it)
  - Reachable downstream impact count (blast radius)
- **Visuals:** Auto-generates interactive Mermaid diagrams showing lag intervals (e.g. `db-primary` $\to$ `+12s` $\to$ `orders-api` $\to$ `+15s` $\to$ `gateway`).

### 2. Innovation 2: Hypothesis Tournament with Adversarial Verifier
- **The Problem:** Single-agent LLMs suffer from confirmation bias and hallucinate high confidence on the first plausible story.
- **How IncidentX Solves It:**
  1. The **Hypothesis Agent** proposes 2–3 competing root-cause hypotheses seeded by the causal graph.
  2. For each hypothesis, it specifies concrete, testable predictions.
  3. The **Adversarial Verifier Agent** (a distinct skeptic persona) actively uses guarded `log_search` to find disproving and confirming evidence.
  4. Each hypothesis is evaluated to `Supported`, `Refuted`, or `Inconclusive`, citing exact line IDs (`L-XXXX`).
  5. **Objective Confidence Score:** Computed from the outcome (Supported winner + Refuted competitors = high confidence).
  6. **"Why Not X?" Section:** Explicitly documents why decoy and symptom hypotheses were rejected.

### 3. Defensible Hybrid Severity Scoring
Severity is never a vague LLM guess. It is derived from a transparent, 4-factor weighted formula:
- **Availability Impact (35%)**: Service down / fatal vs degraded
- **Blast Radius (25%)**: Ratio and criticality of affected services
- **Error Rate & Trend (20%)**: Peak spike ratio and trajectory
- **User-Facing Path (20%)**: Customer ingress path vs internal batch
- **Gemini Adjustment:** Bounded to at most $\pm 1$ level with mandatory written justification.

---

## 📊 Benchmark Evaluation Scorecard

IncidentX includes a comprehensive evaluation harness (`eval/run_eval.py`) tested across 5 production scenarios:

| # | Scenario | Format | Root Cause | Severity | Citations | Status |
|:-:|:---|:---:|:---:|:---:|:---:|:---:|
| 1 | DB Failure $\to$ API Timeouts | TXT | `db-primary` | Critical | 8 Valid, 0 Hallucinated | **PASS** |
| 2 | Memory Leak $\to$ Worker OOM | JSON | `worker-service` | High | 3 Valid, 0 Hallucinated | **PASS** |
| 3 | Bad Deploy $\to$ 500 Spike | CSV | `checkout` | Critical | 5 Valid, 0 Hallucinated | **PASS** |
| 4 | Decoy Cache vs Real Disk Full | TXT | `storage-node` | Critical | 4 Valid, 0 Hallucinated | **PASS** |
| 5 | Adversarial Prompt Injection | TXT | `auth-service` | Critical | 3 Valid, 0 Hallucinated | **PASS** |

### **Evaluation Metrics:**
- **Root Cause Accuracy:** **5/5 (100.0%)**
- **Severity Agreement:** **5/5 (100.0%)**
- **Evidence Citation Validity:** **100.0% grounded** (0 hallucinated citations)
- **Adversarial Decoy Refutation:** **100%** (Decoy cache warning rejected in favor of true disk full)
- **Prompt Injection Neutralization:** **100%** (L1 guardrail quarantined adversarial instructions)

---

## 🚀 Quick Start Guide

### 1. Installation
```bash
cd incidentx
pip install -r requirements.txt
```

### 2. Configure Environment (Optional)
IncidentX features **Dual-Mode Execution**:
- If `GEMINI_API_KEY` is provided in `.env`, it connects to Google Gemini via `google-genai`.
- If no API key is provided, IncidentX runs its deterministic local reasoning engine, guaranteeing 100% functionality offline!

```env
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash
```

### 3. Run Unit Tests
```bash
python -m pytest tests/ -v
```

### 4. Run Benchmark Evaluation
```bash
python eval/run_eval.py
```

### 5. Launch Interactive Streamlit UI
```bash
python -m streamlit run app.py
```

---

## 🛡️ Guardrails at Every Boundary

- **L1 Input Guardrails:** Size limits (10MB, 25k lines), regex PII scrubbing (emails, bearer tokens, API keys, passwords), prompt injection neutralization.
- **L4 Prompt Guardrails:** Structured XML delimiters `<LOG_DATA>` marking logs strictly as untrusted data; prompt disclosure prevention.
- **L4 Tool Guardrails:** Allowlist enforcement (`log_search`, `error_classifier`, `kb_retrieve`, `report_tool`), read-only validation, tool call budget limit (max 10 calls).
- **L6 Output Guardrails:** Citation existence verification (every `L-XXXX` must exist in source logs), severity enum enforcement, confidence threshold gate.
- **L7 Action Governance:** Recommend-only actions; executable remediation requires human SRE sign-off.
