# ─────────────────────────────────────────────
# LAYER 1: RAW COMPUTATION
# ─────────────────────────────────────────────

import os
import itertools

import numpy as np
import pandas as pd

from scipy.stats import pearsonr

from analytics_pipeline.logger import logger
from analytics_pipeline.schema import validate_layer_inputs
from analytics_pipeline.utils import (
    safe_list,
    classify_correlation_strength,
    map_priority_from_score,
    is_identifier_column,
)

# FIX: Prevent O(N^2) timeout on wide datasets. Max 50 cols = 1225 pairs.
MAX_NUMERIC_COLS_FOR_CORRELATION = 50

def generate_profile(state):
    validate_layer_inputs(state, "profile", ["df"])
    df = state["df"]
    profile = {}
    for col in df.columns:
        series = df[col].dropna()
        if series.empty: continue
        try:
            if pd.api.types.is_numeric_dtype(series):
                profile[col] = {"type": "numeric", "mean": round(float(series.mean()), 2), "median": round(float(series.median()), 2), "std": round(float(series.std()), 2), "min": float(series.min()), "max": float(series.max())}
            else:
                profile[col] = {"type": "categorical", "unique_values": int(series.nunique()), "top_value": str(series.value_counts().idxmax())}
        except Exception as e:
            logger.warning(f"Profile skipped {col}: {e}", extra={"layer": "profile"})
    state["profile"] = profile
    return state

def generate_charts(state):
    df = state.get("df")
    state["charts"] = [] 
    state["chart_file"] = None
    state["chart_url"] = None

    if df is None:
        return state

    try:
        # ── CHART 1: Numeric Distribution (Area Chart) ──
        numeric_cols = [c for c in df.select_dtypes(include=[np.number]).columns if not is_identifier_column(c, df[c])]
        if numeric_cols:
            col = numeric_cols[0]
            series = df[col].dropna()
            if len(series) > 0 and series.nunique() > 1:
                counts, bin_edges = np.histogram(series, bins=15)
                labels = [f"{bin_edges[i]:.0f}-{bin_edges[i+1]:.0f}" for i in range(len(counts))]
                state["charts"].append({
                    "title": f"{col} Distribution",
                    "type": "line",
                    "labels": labels,
                    "datasets": [{"label": col, "data": counts.tolist()}]
                })

        # ── CHART 2: Categorical Breakdown (Doughnut) ──
        cat_cols = df.select_dtypes(include=['object', 'category']).columns
        if len(cat_cols) > 0:
            col = cat_cols[0]
            series = df[col].dropna()
            if len(series) > 0:
                counts = series.value_counts().head(6) # Top 6 slices
                state["charts"].append({
                    "title": f"{col} Breakdown",
                    "type": "doughnut",
                    "labels": counts.index.astype(str).tolist(),
                    "datasets": [{"label": col, "data": counts.values.tolist()}]
                })

        # ── CHART 3: Top Correlation (Scatter Plot) ──
        pairs = (state.get("correlations") or {}).get("pairs", [])
        strong_pairs = [p for p in pairs if abs(p.get("pearson", 0)) > 0.3]
        if strong_pairs:
            top_pair = strong_pairs[0]
            pair_names = top_pair["pair"].split(" vs ")
            if len(pair_names) == 2:
                c1, c2 = pair_names[0].strip(), pair_names[1].strip()
                if c1 in df.columns and c2 in df.columns:
                    sample_df = df[[c1, c2]].dropna()
                    # FIX: Prevent ValueError crash if dropna reduces size below sample target
                    sample_n = min(50, len(sample_df))
                    if sample_n > 0:
                        sample_df = sample_df.sample(n=sample_n, random_state=42)
                        state["charts"].append({
                            "title": f"{c1} vs {c2}",
                            "type": "scatter",
                            "labels": [],
                            "datasets": [{
                                "label": f"r={top_pair.get('pearson', 0)}",
                                "data": [{ "x": float(row[c1]), "y": float(row[c2]) } for _, row in sample_df.iterrows()]
                            }]
                        })
    except Exception as e:
        logger.error(f"Chart generation failed: {e}", extra={"layer": "chart"})

    return state

def generate_correlation_analysis(state):
    config = state["config"]
    df = state.get("df")
    results = []
    if df is None: state["correlations"] = {"pairs": results}; return state
    
    numeric_df = df.select_dtypes(include=[np.number]).copy()
    filtered_cols = [c for c in numeric_df.columns if not is_identifier_column(c, numeric_df[c])]
    numeric_df = numeric_df[filtered_cols]
    
    # FIX: Truncate columns to prevent O(N^2) HTTP timeout
    if numeric_df.shape[1] > MAX_NUMERIC_COLS_FOR_CORRELATION:
        logger.warning(f"Truncating correlation matrix from {numeric_df.shape[1]} to {MAX_NUMERIC_COLS_FOR_CORRELATION} cols to prevent timeout", extra={"layer": "correlations"})
        numeric_df = numeric_df.iloc[:, :MAX_NUMERIC_COLS_FOR_CORRELATION]
    
    if numeric_df.shape[1] < 2: state["correlations"] = {"pairs": results}; return state
    
    pearson_corr = numeric_df.corr(method="pearson")
    for col1, col2 in itertools.combinations(numeric_df.columns, 2):
        val = pearson_corr.loc[col1, col2]
        if pd.isna(val): continue  # FIX: Skip NaN correlations instead of converting to 0.0
        try:
            c1, c2 = numeric_df[col1].dropna(), numeric_df[col2].dropna()
            idx = c1.index.intersection(c2.index)
            p_value = pearsonr(c1.loc[idx], c2.loc[idx])[1] if len(idx) >= 3 else 1.0
        except Exception:  # FIX: Never bare 'except'
            p_value = 1.0
        
        significance = "not significant"
        if p_value < 0.01: significance = "highly significant"
        elif p_value < 0.05: significance = "significant"
        
        results.append({"pair": f"{col1} vs {col2}", "pearson": round(float(val), 3), "strength": classify_correlation_strength(val), "p_value": round(float(p_value), 5), "significance": significance})
    
    state["correlations"] = {"pairs": results}
    return state

def generate_dataset_health(state):
    df = state.get("df")
    if df is None: 
        state["dataset_health"] = {"completeness_score": 0.0, "anomaly_count": 0, "dominance_issues": 0, "health_score": 0.0}
        return state
    
    total_cells = df.shape[0] * df.shape[1]
    missing = int(df.isna().sum().sum())
    completeness = 1 - (missing / total_cells if total_cells > 0 else 0)
    
    state["dataset_health"] = {
        "completeness_score": round(completeness, 3), 
        "anomaly_count": 0, 
        "dominance_issues": 0, 
        "health_score": round(max(0.0, min(100.0, completeness * 100)), 2)
    }
    return state

def detect_anomalies(state):
    df = state.get("df")
    state["anomaly_details"] = []
    if df is None: return state
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    row_mask = pd.Series(False, index=df.index)
    for col in numeric_cols:
        if is_identifier_column(col, df[col]): continue
        series = df[col].dropna()
        if len(series) < 5: continue
        q1, q3 = series.quantile(0.25), series.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0 or pd.isna(iqr): continue
        mask = (df[col] < (q1 - 1.5 * iqr)) | (df[col] > (q3 + 1.5 * iqr))
        cnt = int(mask.sum())
        if cnt > 0:
            state["anomaly_details"].append({"column": col, "count": cnt, "pct": round(cnt / max(1, len(series)), 4)})
            row_mask |= mask.fillna(False)
    state["dataset_health"]["anomaly_count"] = int(row_mask.sum())
    return state

def resolve_conflicts(state):
    conflicts = []
    corr = safe_list((state.get("correlations") or {}).get("pairs"))
    health = state.get("dataset_health") or {}
    hs = float(health.get("health_score", 0))
    rows = state.get("rows", 0)
    ac = int(health.get("anomaly_count", 0))
    
    strong = [p for p in corr if p.get("strength") in ("strong", "very strong")]
    if strong and hs < 60: conflicts.append({"type": "correlation_vs_health", "severity": "high", "message": "Strong correlations but low health."})
    if rows < 10 and corr: conflicts.append({"type": "sample_size_warning", "severity": "medium", "message": f"Small dataset (n={rows})."})
    if ac > 0: conflicts.append({"type": "anomalies_detected", "severity": "medium", "message": f"{ac} anomaly events detected."})
    
    state["conflicts"] = conflicts
    return state

def compute_insight_confidence(sig, n, hs, sv, cc, config):
    conf = 0.4 * config.significance_scores.get(sig, 0.2) + 0.3 * (0.95 if n >= 100000 else 0.4 if n < 100 else 0.7) + 0.2 * min(1.0, hs / 100.0) + 0.1 * min(1.0, sv)
    return max(0.05, min(1.0, conf - min(0.15, cc * 0.03)))

def generate_ranked_insights(state):
    config = state["config"]
    pairs = (state.get("correlations") or {}).get("pairs") or []
    raw = []
    n, hs, cc = state.get("rows", 0), (state.get("dataset_health") or {}).get("health_score", 50), len(state.get("conflicts") or [])
    
    for item in pairs:
        sv = abs(item.get("pearson", 0))
        sig = item.get("significance", "not significant")
        conf = compute_insight_confidence(sig, n, hs, sv, cc, config)
        raw.append({"type": "correlation", "priority": "high" if sv > 0.7 else "medium" if sv >= 0.35 and sig == "highly significant" else "low", "score": round(sv, 3), "strength": item.get("strength"), "strength_value": sv, "pearson": item.get("pearson", 0), "significance": sig, "confidence": conf, "p_value": item.get("p_value"), "pair": item.get("pair", "")})
    
    raw.sort(key=lambda x: x.get("score", 0), reverse=True)
    state["raw_signals"] = raw[:config.max_raw_signals]
    return state

def calibrate_confidence(state):
    raw = state.get("raw_signals") or []
    hs = (state.get("dataset_health") or {}).get("health_score", 0)
    n, cc, ac = state.get("rows", 0), len(state.get("conflicts") or []), (state.get("dataset_health") or {}).get("anomaly_count", 0)
    config = state["config"]
    
    for item in raw:
        base = float(item.get("confidence", 0.5))
        score = base * config.strength_bonuses.get(item.get("strength", "weak"), 1.0)
        
        size_multiplier = (
            0.65 if n < 5 else
            0.78 if n < 10 else
            0.88 if n < 30 else
            0.95 if n < 100 else
            1.0
        )
        score *= size_multiplier
        score *= (0.75 + (min(1.0, hs / 100) * 0.25))
        score *= (1 - min(0.20, cc * 0.05))
        score *= (1 - min(0.15, ac * 0.03))
        
        item["confidence"] = round(max(0.1, min(score, 0.95)), 3)
        item["priority"] = map_priority_from_score(item["confidence"])
    state["raw_signals"] = raw
    return state

def deduplicate_insights(state):
    seen, cleaned = set(), []
    for item in (state.get("raw_signals") or []):
        key = item.get("pair", "").lower().strip()
        if key not in seen: seen.add(key); cleaned.append(item)
    state["raw_signals"] = cleaned
    return state

def rebalance_scores(state):
    config = state["config"]
    hs = (state.get("dataset_health") or {}).get("health_score", 0)
    n, cc = state.get("rows", 0), len(state.get("conflicts") or [])
    sf, cf, hf = min(n / 50, 1), max(0, 1 - cc * 0.1), hs / 100
    
    for item in (state.get("raw_signals") or []):
        s = item.get("score", 0)
        sens = config.insight_sensitivity.get(item.get("type", "unknown"), {"dataset_size_weight": 0.5, "conflict_penalty_weight": 0.5, "health_weight": 0.5})
        s *= (1 - sens["dataset_size_weight"] + sens["dataset_size_weight"] * sf)
        s *= (1 - sens["conflict_penalty_weight"] + sens["conflict_penalty_weight"] * cf)
        s *= (1 - sens["health_weight"] + sens["health_weight"] * hf)
        item["score"] = round(s, 3)
    return state