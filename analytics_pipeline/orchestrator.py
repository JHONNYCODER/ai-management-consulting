import time
import traceback
import pandas as pd
import numpy as np

from dataclasses import dataclass
from typing import Dict, List

from .config import PipelineConfig
from .schema import (
    create_initial_state,
    validate_layer_inputs
)
from .exceptions import (
    PipelineError,
    ComputationError
)
from .logger import logger

from .layers.raw_computation import (
    generate_profile,
    generate_chart,
    generate_correlation_analysis,
    generate_dataset_health,
    detect_anomalies,
    resolve_conflicts,
    generate_ranked_insights,
    calibrate_confidence,
    deduplicate_insights,
    rebalance_scores
)

from .layers.normalization import (
    normalize_signals,
    generate_signal_taxonomy
)

from .layers.structuring import (
    generate_contextual_synthesis,
    generate_theme_metrics
)

from .layers.reasoning import (
    generate_derived_signals,
    generate_analytical_stability,
    generate_cross_theme_reasoning
)

from .layers.decision import (
    generate_executive_synthesis,
    generate_structured_reasoning
)

from .layers.output import (
    generate_narrative_summary,
    generate_final_insights,
    generate_recommendations
)

from .ai_readiness import (
    build_ai_context,
    build_llm_payload
)

# ─────────────────────────────────────────────
# PART 2: PIPELINE ORCHESTRATION ENGINE
# ─────────────────────────────────────────────

@dataclass
class PipelineExecutionResult:
    state: Dict
    success: bool
    layers_executed: List[str]
    layers_failed: List[Dict]
    execution_duration_ms: float
    diagnostics: Dict

# PART 4: DIAGNOSTICS
def generate_pipeline_diagnostics(state):
    trace = state.get("layer_execution_trace", {})
    durations = {k: v.get("duration_ms", 0) for k, v in trace.items()}
    state["diagnostics"] = {"slowest_layer": max(durations, key=durations.get) if durations else None}
    return state

PIPELINE_REGISTRY = [
    {"name": "profile", "fn": generate_profile, "requires": ["df"]},
    {"name": "correlations", "fn": generate_correlation_analysis, "requires": ["df"]},
    {"name": "dataset_health", "fn": generate_dataset_health, "requires": ["df"]},
    {"name": "anomalies", "fn": detect_anomalies, "requires": ["df"]},
    {"name": "conflicts", "fn": resolve_conflicts, "requires": ["correlations", "dataset_health"]},
    {"name": "raw_signals", "fn": generate_ranked_insights, "requires": ["correlations", "dataset_health", "conflicts"]},
    {"name": "calibrate", "fn": calibrate_confidence, "requires": ["raw_signals"]},
    {"name": "deduplication", "fn": deduplicate_insights, "requires": ["raw_signals"]},
    {"name": "rebalance", "fn": rebalance_scores, "requires": ["raw_signals"]},
    {"name": "normalize_signals", "fn": normalize_signals, "requires": ["raw_signals"]},
    {"name": "signal_taxonomy", "fn": generate_signal_taxonomy, "requires": ["profile"]},
    {"name": "contextual_synthesis", "fn": generate_contextual_synthesis, "requires": ["raw_signals", "signal_taxonomy"]},
    {"name": "theme_metrics", "fn": generate_theme_metrics, "requires": ["contextual_synthesis"]},
    {"name": "derived_signals", "fn": generate_derived_signals, "requires": ["raw_signals"]},
    {"name": "analytical_stability", "fn": generate_analytical_stability, "requires": ["raw_signals", "dataset_health", "conflicts"]},
    {"name": "cross_theme_reasoning", "fn": generate_cross_theme_reasoning, "requires": ["theme_metrics", "conflicts"]},
    
    # FIX: executive_synthesis MUST come before structured_reasoning
    {"name": "executive_synthesis", "fn": generate_executive_synthesis, "requires": ["cross_theme_reasoning", "analytical_stability", "raw_signals", "theme_metrics"]},
    {"name": "structured_reasoning", "fn": generate_structured_reasoning, "requires": ["raw_signals", "theme_metrics", "executive_synthesis"]},
    
    {"name": "narrative_summary", "fn": generate_narrative_summary, "requires": ["executive_synthesis", "analytical_stability"]},
    {"name": "final_insights", "fn": generate_final_insights, "requires": ["executive_synthesis"]},
    {"name": "recommendations", "fn": generate_recommendations, "requires": ["executive_synthesis", "theme_metrics", "signal_taxonomy"]},
    {"name": "ai_context", "fn": build_ai_context, "requires": ["executive_synthesis"]},
    {"name": "llm_payload", "fn": build_llm_payload, "requires": ["ai_context"]},
    {"name": "diagnostics", "fn": generate_pipeline_diagnostics, "requires": ["layer_execution_trace"]},
]

def execute_pipeline_layer(state: Dict, layer_def: Dict, config: PipelineConfig) -> Dict:
    name, fn, reqs = layer_def["name"], layer_def["fn"], layer_def.get("requires", [])
    start_time = time.time()
    
    try:
        validate_layer_inputs(state, name, reqs)
        input_size = len(state.get("raw_signals", [])) if "raw_signals" in reqs else 0
        state = fn(state)
        duration = round((time.time() - start_time) * 1000, 2)
        
        state["layer_execution_trace"][name] = {"status": "success", "duration_ms": duration, "input_size": input_size}
        logger.info(f"Layer {name} completed", extra={"layer": name, "duration_ms": duration})
        return state
    except PipelineError as e:
        duration = round((time.time() - start_time) * 1000, 2)
        state["layer_execution_trace"][name] = {"status": "failed", "duration_ms": duration, "error": e.root_cause}
        logger.error(f"Layer {name} failed: {e.root_cause}", extra={"layer": name})
        if config.execution_mode == "fail_fast": raise
        return state
    except Exception as e:
        duration = round((time.time() - start_time) * 1000, 2)
        tb = traceback.format_exc()
        state["layer_execution_trace"][name] = {"status": "failed", "duration_ms": duration, "error": str(e)}
        logger.error(f"Layer {name} raw exception: {str(e)}", extra={"layer": name})
        if config.execution_mode == "fail_fast":
            raise ComputationError(name, fn.__name__, str(e), False, tb, {}) from e
        return state

def run_pipeline(file_path: str, config: PipelineConfig = None) -> PipelineExecutionResult:
    config = config or PipelineConfig()
    df = pd.read_csv(file_path)
    state = create_initial_state(df=df, file_path=file_path, config=config)
    
    start_time = time.time()
    executed, failed = [], []
    
    state["output_dir"] = config.output_dir or "uploads"
    # Chart generation is handled outside the strict registry due to dynamic column selection
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    chart_col = numeric_cols[0] if numeric_cols else None
    if chart_col: state = generate_chart(state, chart_col)
    
    for layer_def in PIPELINE_REGISTRY:
        try:
            state = execute_pipeline_layer(state, layer_def, config)
            executed.append(layer_def["name"])
        except PipelineError as e:
            failed.append({"layer": e.layer, "error": e.root_cause})
            if config.execution_mode == "fail_fast": break
            
    duration_ms = round((time.time() - start_time) * 1000, 2)
    state["metadata"] = {"pipeline_version": "2.0.0", "execution_duration_ms": duration_ms, "layers_executed": executed, "layers_failed": failed}
    
    return PipelineExecutionResult(
        state=state, success=len(failed) == 0, layers_executed=executed, layers_failed=failed, execution_duration_ms=duration_ms, diagnostics=state.get("diagnostics", {})
    )