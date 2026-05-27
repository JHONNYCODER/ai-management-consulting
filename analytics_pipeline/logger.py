# ─────────────────────────────────────────────
# PART 4: LOGGING + OBSERVABILITY
# ─────────────────────────────────────────────
import json
import logging
import os
from datetime import datetime, timezone

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "layer": getattr(record, "layer", "pipeline"),
            "message": record.getMessage(),
            "duration_ms": getattr(record, "duration_ms", None),
            "input_size": getattr(record, "input_size", None),
            "output_size": getattr(record, "output_size", None),
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_record)

# ── PATH SETUP ──
# Assumes this file is: project_root/analytics_pipeline/logger.py
# Targets: project_root/backend/logs/pipeline.log
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(PROJECT_ROOT, "backend", "logs")
LOG_FILE = os.path.join(LOG_DIR, "pipeline.log")

# Create log directory if it doesn't exist
os.makedirs(LOG_DIR, exist_ok=True)

logger = logging.getLogger("analytics_pipeline")

# Prevent duplicate handlers on hot-reloads (uvicorn / flask)
if logger.handlers:
    logger.handlers.clear()

# 1. FILE HANDLER (DEBUG level - catches EVERY layer execution log)
file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(JSONFormatter())
logger.addHandler(file_handler)

# 2. TERMINAL HANDLER (INFO level - hides layer noise, shows lifecycle events)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(JSONFormatter())
logger.addHandler(console_handler)

# 3. Set root logger to DEBUG so it passes both levels to the handlers
logger.setLevel(logging.DEBUG)