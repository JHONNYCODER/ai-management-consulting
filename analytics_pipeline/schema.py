import uuid
import pandas as pd

from datetime import datetime, timezone
from typing import Dict, List

from analytics_pipeline.config import PipelineConfig
from analytics_pipeline.cache import PipelineCache
from analytics_pipeline.exceptions import ValidationError

# ─────────────────────────────────────────────
# PART 1: STATE CONTRACT & SCHEMA
# ─────────────────────────────────────────────

STATE_SCHEMA = {
    # Internal / Raw
    "df":                    {"type": (pd.DataFrame, type(None)), "required": False},
    "file_path":             {"type": (str, type(None)),           "required": False},
    "output_dir":            {"type": (str, type(None)),           "required": False},
    "rows":                  {"type": int,                         "required": True},
    "columns":               {"type": int,                         "required": True},
    "insights_input":        {"type": dict,                        "required": False},
    
    # Layer Outputs
    "profile":               {"type": dict,                        "required": True},
    "chart_path":            {"type": (str, type(None)),           "required": False},
    "chart_file":            {"type": (str, type(None)),           "required": False},
    "chart_url":             {"type": (str, type(None)),           "required": False},
    "correlations":          {"type": dict,                        "required": True},
    "dataset_health":        {"type": dict,                        "required": True},
    "anomaly_details":       {"type": list,                        "required": True},
    "conflicts":             {"type": list,                        "required": True},
    "raw_signals":           {"type": list,                        "required": True},
    "derived_signal_view":   {"type": list,                        "required": True},
    "signal_taxonomy":       {"type": dict,                        "required": True},
    "semantic_insights":     {"type": list,                        "required": False},
    "insights":              {"type": list,                        "required": False},
    "analytical_stability":  {"type": dict,                        "required": True},
    "narrative_summary":     {"type": dict,                        "required": True},
    "final_insights":        {"type": dict,                        "required": True},
    "contextual_synthesis":  {"type": dict,                        "required": True},
    "theme_metrics":         {"type": dict,                        "required": True},
    "cross_theme_reasoning": {"type": dict,                        "required": True},
    "executive_synthesis":   {"type": dict,                        "required": True},
    "recommendations":       {"type": dict,                        "required": True},
    "structured_reasoning":  {"type": dict,                        "required": True},
    "ai_context":            {"type": dict,                        "required": False},
    "llm_payload":           {"type": (dict, type(None)),          "required": False},
    
    # Meta & System
    "validation":            {"type": dict,                        "required": False},
    "metadata":              {"type": dict,                        "required": False},
    "state_version":         {"type": str,                         "required": True},
    "pipeline_run_id":       {"type": str,                         "required": True},
    "execution_timestamp":   {"type": str,                         "required": True},
    "layer_execution_trace": {"type": dict,                        "required": True},
    "pipeline_cache":        {"type": PipelineCache,               "required": True},
    "config":                {"type": PipelineConfig,              "required": True},
}

def validate_required_keys(state: Dict, keys: List[str]) -> bool:
    missing = [k for k in keys if k not in state or state[k] is None]
    if missing:
        raise ValidationError(
            layer="validation", function="validate_required_keys",
            root_cause=f"Missing required keys: {missing}",
            recoverable=False, trace="", context={"missing": missing}
        )
    return True

def validate_layer_inputs(state: Dict, layer_name: str, required_inputs: List[str]) -> bool:
    try:
        return validate_required_keys(state, required_inputs)
    except ValidationError as e:
        e.layer = layer_name
        raise e

def validate_state_contract(state: Dict, strict: bool = True) -> Dict:
    errors = []
    if not isinstance(state, dict):
        return {"valid": False, "errors": ["State is not a dictionary"]}
    
    if strict:
        for key, spec in STATE_SCHEMA.items():
            if spec.get("required", False) and key not in state:
                errors.append(f"Missing required key: {key}")
            elif key in state and state[key] is not None:
                expected = spec["type"]
                if not isinstance(expected, tuple): expected = (expected,)
                if not isinstance(state[key], expected):
                    errors.append(f"Key '{key}' wrong type: expected {spec['type']}, got {type(state[key]).__name__}")
        
        exec_conf = state.get("executive_synthesis", {}).get("confidence")
        if exec_conf is not None and not (0 <= exec_conf <= 1):
            errors.append(f"Executive confidence out of range (0-1): {exec_conf}")
            
    return {"valid": len(errors) == 0, "errors": errors}

# ─────────────────────────────────────────────
# STATE INITIALIZATION
# ─────────────────────────────────────────────

def create_initial_state(df=None, file_path=None, insights_input=None, config: PipelineConfig = None):
    config = config or PipelineConfig()
    return {
        "df": df, "file_path": file_path,
        "rows": len(df) if df is not None else 0,
        "columns": len(df.columns) if df is not None else 0,
        "insights_input": insights_input or {"summary": [], "metrics": []},
        "output_dir": None, # Added for orchestrator
        "profile": {}, 
        "chart_path": None, 
        "chart_file": None, # Added for raw_computation
        "chart_url": None,  # Added for raw_computation
        "correlations": {"pairs": []},
        "dataset_health": {"health_score": 0, "completeness_score": 0.0, "anomaly_count": 0, "dominance_issues": 0},
        "anomaly_details": [], "conflicts": [],
        "raw_signals": [], "derived_signal_view": [], "signal_taxonomy": {},
        "semantic_insights": [], "insights": [],
        "analytical_stability": {"system_health_score": 0, "signal_confidence_score": 0.0, "stability_index": 0, "label": "unknown", "summary": ""},
        "narrative_summary": {}, "final_insights": {"key_findings": [], "supporting_evidence": [], "warnings": [], "summary": ""},
        "contextual_synthesis": {}, "theme_metrics": {"themes": [], "overall_strength_bundle": {}},
        "cross_theme_reasoning": {}, "executive_synthesis": {}, "recommendations": {},
        "ai_context": {}, "structured_reasoning": {}, "llm_payload": None, "validation": {}, "metadata": {},
        
        # PART 1 ADDITIONS
        "state_version": "4.0",
        "pipeline_run_id": str(uuid.uuid4()),
        "execution_timestamp": datetime.now(timezone.utc).isoformat(),
        "layer_execution_trace": {},
        "pipeline_cache": PipelineCache(),
        "config": config
    }