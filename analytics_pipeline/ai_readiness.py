from typing import Dict, Any

# ─────────────────────────────────────────────
# PART 8: AI READINESS
# ─────────────────────────────────────────────

def _clean_for_llm(data: Any) -> Any:
    """
    Recursively strips out internal keys (like IDs), empty dicts, 
    and empty lists to save tokens and reduce LLM confusion.
    """
    if isinstance(data, dict):
        cleaned = {}
        for k, v in data.items():
            # Skip internal IDs and pipeline-specific meta keys
            if k in ("driver_id", "theme_id", "pipeline_run_id", "state_version"):
                continue
            cleaned_v = _clean_for_llm(v)
            # Only include if it's not empty
            if cleaned_v is not None and cleaned_v != [] and cleaned_v != {}:
                cleaned[k] = cleaned_v
        return cleaned
    elif isinstance(data, list):
        return [_clean_for_llm(item) for item in data if item is not None]
    return data

def build_ai_context(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepares a condensed, clean context for the LLM.
    We only include what the AI actually needs to generate insights.
    """
    exec_s = _clean_for_llm(state.get("executive_synthesis", {}))
    themes = _clean_for_llm(state.get("theme_metrics", {}).get("dominant_themes", []))
    stability = _clean_for_llm(state.get("analytical_stability", {}))
    
    state["ai_context"] = {
        "executive": exec_s,
        "dominant_themes": themes,
        "stability": stability
    }
    return state

def build_llm_payload(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Builds the final JSON payload that will be sent directly to the LLM API.
    Includes a system prompt so the LLM knows its role.
    """
    context = state.get("ai_context", {})
    recommendations = _clean_for_llm(state.get("recommendations", {}))
    
    system_prompt = (
        "You are an expert management consultant AI. "
        "Your task is to analyze the provided data context and recommendations, "
        "then generate a concise, actionable executive summary. "
        "Highlight the key drivers, acknowledge the risks, and suggest next steps. "
        "Do not invent data; only use what is provided."
    )
    
    state["llm_payload"] = {
        "schema_version": "4.0",
        "system_prompt": system_prompt,
        "context": context,
        "recommendations": recommendations
    }
    return state