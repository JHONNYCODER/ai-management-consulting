import os
from typing import Dict, Any
from backend.schemas.analytics_response import (
    AnalyticsResponse,
    AnalyticsResponseData,
    Summary,
    ProfileMetric,
    CorrelationPair,
    DatasetHealth,
    ExecutiveSynthesis
)

def safe_get(d: Dict, key: str, default: Any = None) -> Any:
    """Safely get a value from a dictionary."""
    return d.get(key, default) if isinstance(d, dict) else default

def _filter_themes(themes: list) -> list:
    """Removes themes with no supporting signals (noise)."""
    return [
        t for t in themes 
        if isinstance(t, dict) and t.get("supporting_signals") and len(t.get("supporting_signals", [])) > 0
    ]

def _clean_profile_metric(data: dict) -> dict:
    """Strips irrelevant keys based on column type."""
    col_type = data.get("type")
    if col_type == "categorical":
        return {k: v for k, v in data.items() if k in ("type", "unique_values", "top_value")}
    elif col_type == "numeric":
        return {k: v for k, v in data.items() if k in ("type", "mean", "median", "std", "min", "max")}
    return data

def map_state_to_api_response(state: Dict) -> AnalyticsResponse:
    """Maps the internal pipeline state to a clean, lean external API response."""
    
    # 1. Summary
    summary = Summary(
        rows=safe_get(state, "rows", 0),
        columns=safe_get(state, "columns", 0)
    )
    
    # 2. Profile
    raw_profile = safe_get(state, "profile", {})
    profile = {
        k: ProfileMetric(**_clean_profile_metric(v)) 
        for k, v in raw_profile.items() if isinstance(v, dict)
    }
    
    # 3. Correlations
    raw_pairs = safe_get(safe_get(state, "correlations", {}), "pairs", [])
    correlations = {
        "pairs": [CorrelationPair(**p) for p in raw_pairs if isinstance(p, dict)]
    }
    
    # 4. Health
    raw_health = safe_get(state, "dataset_health", {})
    dataset_health = DatasetHealth(
        completeness_score=safe_get(raw_health, "completeness_score", 0.0),
        anomaly_count=safe_get(raw_health, "anomaly_count", 0),
        dominance_issues=safe_get(raw_health, "dominance_issues", 0),
        health_score=safe_get(raw_health, "health_score", 0.0)
    )
    
    # 5. Executive Synthesis
    raw_exec = safe_get(state, "executive_synthesis", {})
    executive_synthesis = ExecutiveSynthesis(
        executive_summary=safe_get(raw_exec, "executive_summary", "Analysis incomplete."),
        decision_frame=safe_get(raw_exec, "decision_frame", "N/A"),
        key_drivers=safe_get(raw_exec, "key_drivers", []),
        confidence=safe_get(raw_exec, "confidence", 0.0),
        score=safe_get(raw_exec, "score", 0.0),
        stability_label=safe_get(raw_exec, "stability_label", "unknown")
    )
    
    # 6. Clean Analytical Stability
    raw_stability = safe_get(state, "analytical_stability", {})
    clean_stability = {
        "system_health_score": safe_get(raw_stability, "system_health_score", 0),
        "signal_confidence_score": safe_get(raw_stability, "signal_confidence_score", 0),
        "stability_index": safe_get(raw_stability, "stability_index", 0),
        "label": safe_get(raw_stability, "label", "unknown"),
        "summary": safe_get(raw_stability, "summary", "")
    }
    
    # 7. Clean Contextual Synthesis (Filter empty themes)
    raw_contextual = safe_get(state, "contextual_synthesis", {})
    clean_themes = _filter_themes(safe_get(raw_contextual, "themes", []))
    clean_contextual = {
        "themes": clean_themes,
        "cross_variable_patterns": safe_get(raw_contextual, "cross_variable_patterns", [])
    }
    
    # 8. Clean Theme Metrics (Filter empty themes)
    raw_tm = safe_get(state, "theme_metrics", {})
    clean_tm = {
        "themes": _filter_themes(safe_get(raw_tm, "themes", [])),
        "structural_strength": safe_get(raw_tm, "structural_strength", 0),
        "overall_strength_bundle": safe_get(raw_tm, "overall_strength_bundle", {})
    }
    
    # 9. Clean Cross Theme Reasoning (Fix Ghost Themes)
    raw_ctr = safe_get(state, "cross_theme_reasoning", {})
    valid_theme_names = {t.get("theme") for t in clean_themes} # Get names of surviving themes
    
    raw_interactions = safe_get(raw_ctr, "theme_interactions", [])
    clean_interactions = [
        i for i in raw_interactions 
        if isinstance(i, dict) and i.get("theme_a") in valid_theme_names and i.get("theme_b") in valid_theme_names
    ]
    
    clean_ctr = {
        "theme_interactions": clean_interactions,
        "conflict_pressure": safe_get(raw_ctr, "conflict_pressure", 0),
        "structural_strength": safe_get(raw_ctr, "structural_strength", 0)
    }
    
    # 10. Clean Recommendations (Strip driver_id)
    raw_recs = safe_get(state, "recommendations", {})
    raw_recs_list = raw_recs.get("recommendations", [])
    clean_recs_list = [
        {k: v for k, v in r.items() if k != "driver_id"} 
        for r in raw_recs_list if isinstance(r, dict)
    ]
    clean_recs = {
        "recommendations": clean_recs_list,
        "total_recommendations": raw_recs.get("total_recommendations", 0),
        "system_confidence": raw_recs.get("system_confidence", 0.0)
    }
    
    # 11. Build final data object
    file_name = os.path.basename(safe_get(state, "file_path", "unknown.csv"))

    
    data = AnalyticsResponseData(
        file_name=file_name,
        summary=summary,
        profile=profile,
        correlations=correlations,
        anomaly_details=safe_get(state, "anomaly_details", []),
        dataset_health=dataset_health,
        analytical_stability=clean_stability,
        conflicts=safe_get(state, "conflicts", []),
        contextual_synthesis=clean_contextual,
        cross_theme_reasoning=clean_ctr,
        narrative_summary=safe_get(state, "narrative_summary", {}),
        final_insights=safe_get(state, "final_insights", {}),
        executive_synthesis=executive_synthesis,
        recommendations=clean_recs,
        chart_url=safe_get(state, "chart_url"),
        chart_path=safe_get(state, "chart_file"),
        chart_data=safe_get(state, "chart_data")
    )
    
    # 12. Wrap in top-level response
    success = len(safe_get(state, "metadata", {}).get("layers_failed", [])) == 0
    
    return AnalyticsResponse(
        status="success" if success else "partial_success",
        data=data
    )