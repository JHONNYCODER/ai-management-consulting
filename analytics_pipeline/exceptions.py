# ─────────────────────────────────────────────
# PART 3: STRUCTURED ERROR SYSTEM
# ─────────────────────────────────────────────

from typing import Dict

class PipelineError(Exception):
    def __init__(self, layer: str, function: str, root_cause: str, recoverable: bool, trace: str, context: Dict):
        self.layer = layer
        self.function = function
        self.root_cause = root_cause
        self.recoverable = recoverable
        self.trace = trace
        self.context = context
        super().__init__(f"[{layer}] {function}: {root_cause}")

    def to_dict(self) -> Dict:
        """Easily serialize errors for logging or API responses."""
        return {
            "layer": self.layer,
            "function": self.function,
            "root_cause": self.root_cause,
            "recoverable": self.recoverable,
            "context": self.context
        }

class ValidationError(PipelineError): pass
class ComputationError(PipelineError): pass
class SerializationError(PipelineError): pass
class DependencyError(PipelineError): pass
class InsightGenerationError(PipelineError): pass