# ─────────────────────────────────────────────
# PART 4: LOGGING + OBSERVABILITY
# ─────────────────────────────────────────────
import json
import logging

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

logger = logging.getLogger("analytics_pipeline")

handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())

if not logger.handlers:
    logger.addHandler(handler)

logger.setLevel(logging.INFO)