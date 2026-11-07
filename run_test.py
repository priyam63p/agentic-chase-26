import sys
import json
from pathlib import Path
sys.path.append(str(Path(__file__).parent))
from core.orchestrator import PipelineOrchestrator
from config import SAMPLE_LOGS_DIR
# use first sample log
files = list(SAMPLE_LOGS_DIR.glob('*'))
if not files:
    print('No sample logs')
    sys.exit(1)
fp = files[0]
raw = fp.read_text(encoding='utf-8')
fmt = fp.suffix.lstrip('.')
orc = PipelineOrchestrator()
rep = orc.run_investigation(raw, fp.name, fmt)
print('Incident ID:', rep.incident_id)
print('Root cause:', rep.root_cause_service)
print('Severity:', rep.severity.final_severity.value)
