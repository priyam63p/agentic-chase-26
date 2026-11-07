import os
from pathlib import Path
from dotenv import load_dotenv

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# LLM Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Directories
DATA_DIR = BASE_DIR / "data"
SAMPLE_LOGS_DIR = DATA_DIR / "sample_logs"
EXPECTED_DIR = DATA_DIR / "expected"
KNOWLEDGE_BASE_DIR = BASE_DIR / "knowledge_base"
RUNBOOKS_PATH = KNOWLEDGE_BASE_DIR / "runbooks.json"
INCIDENT_MEMORY_PATH = KNOWLEDGE_BASE_DIR / "incident_memory.json"
OUTPUTS_DIR = BASE_DIR / "outputs"
REPORTS_DIR = OUTPUTS_DIR / "reports"
AUDIT_LOG_PATH = OUTPUTS_DIR / "audit.log"

# Guardrail & Safety Limits
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_LOG_LINES = 25000
ALLOWED_EXTENSIONS = {".txt", ".json", ".csv", ".log"}
MAX_TOOL_CALL_BUDGET = 10
TOOL_TIMEOUT_SECONDS = 15
MIN_CONFIDENCE_THRESHOLD = 0.60

# Processing & Detection Thresholds
DEFAULT_WINDOW_SECONDS = 30
ANOMALY_RATIO_THRESHOLD = 0.15
ZSCORE_THRESHOLD = 2.0
CAUSAL_LAG_WINDOW_SECONDS = 180

# Hybrid Severity Weights (Must sum to 1.0)
SEVERITY_WEIGHTS = {
    "availability_impact": 0.35,
    "blast_radius": 0.25,
    "error_rate_trend": 0.20,
    "user_facing": 0.20
}

# Severity Score Bands
SEVERITY_BANDS = [
    (0.00, 0.25, "Low"),
    (0.25, 0.50, "Medium"),
    (0.50, 0.75, "High"),
    (0.75, 1.01, "Critical")
]

CRITICAL_SERVICES = {"orders-api", "payment-service", "checkout", "auth-service", "api-gateway"}
USER_FACING_SERVICES = {"web", "gateway", "checkout", "orders-api", "auth-service", "frontend"}
