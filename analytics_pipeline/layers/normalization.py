# ─────────────────────────────────────────────
# LAYER 2: NORMALIZATION + TAXONOMY
# ─────────────────────────────────────────────

from analytics_pipeline.utils import (
    _clean_float,
    _assign_tags,
)

def normalize_signals(state):
    """Clamps all numerical signals to their mathematical bounds. Leaves None as None."""
    for item in (state.get("raw_signals") or []):
        # Handle pearson (-1.0 to 1.0)
        p_val = _clean_float(item.get("pearson"))
        item["pearson"] = max(-1.0, min(1.0, p_val)) if p_val is not None else None
        
        # Handle confidence (0.0 to 1.0)
        c_val = _clean_float(item.get("confidence"))
        item["confidence"] = max(0.0, min(1.0, c_val)) if c_val is not None else None
        
        # Handle score (0.0 to 1.0)
        s_val = _clean_float(item.get("score"))
        item["score"] = max(0.0, min(1.0, s_val)) if s_val is not None else None
        
    return state

def generate_signal_taxonomy(state):
    """Maps columns to semantic tags based on config keywords."""
    config = state["config"]
    state["signal_taxonomy"] = {col: _assign_tags(col, config) for col in state.get("profile", {})}
    return state