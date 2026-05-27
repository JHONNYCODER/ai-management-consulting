# ─────────────────────────────────────────────
# LAYER 2: NORMALIZATION + TAXONOMY
# ─────────────────────────────────────────────

from analytics_pipeline.utils import (
    _clean_float,
    _assign_tags,
)

def normalize_signals(state):
    """Clamps all numerical signals to their mathematical bounds."""
    for item in (state.get("raw_signals") or []):
        item["pearson"] = max(-1.0, min(1.0, _clean_float(item.get("pearson", 0))))
        item["confidence"] = max(0.0, min(1.0, _clean_float(item.get("confidence", 0.5))))
        item["score"] = max(0.0, min(1.0, _clean_float(item.get("score", 0)))) # Added score clamping
    return state

def generate_signal_taxonomy(state):
    """Maps columns to semantic tags based on config keywords."""
    config = state["config"]
    state["signal_taxonomy"] = {col: _assign_tags(col, config) for col in state.get("profile", {})}
    return state