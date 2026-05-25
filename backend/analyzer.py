import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import time
import itertools
import re
import math
from scipy.stats import pearsonr
from collections import defaultdict
from datetime import datetime, timezone

# ─────────────────────────────────────────────
# THRESHOLDS
# ─────────────────────────────────────────────

CLUSTER_SIGNAL_THRESHOLD = 0.25
WEAK_SIGNAL_FILTER = 0.10

# ─────────────────────────────────────────────
# VERSIONING
# ─────────────────────────────────────────────

PIPELINE_VERSION = "2.0.0"
SCHEMA_VERSION = "4.0"

# ─────────────────────────────────────────────
# GLOBAL ARCHITECTURE CONTRACT
# ─────────────────────────────────────────────

CONFIDENCE_SCALE = "0_1"
SIGNAL_RANGE = "-1_to_1"
STABILITY_RANGE = "0_100"
HEALTH_RANGE = "0_100"

# ─────────────────────────────────────────────
# STATE SCHEMA ENFORCEMENT
# ─────────────────────────────────────────────

STATE_SCHEMA = {
    "df":                    {"type": (pd.DataFrame, type(None)), "required": False},
    "file_path":             {"type": (str, type(None)),           "required": False},
    "rows":                  {"type": int,                         "required": True},
    "columns":               {"type": int,                         "required": True},
    "insights_input":        {"type": dict,                        "required": False},
    "profile":               {"type": dict,                        "required": True},
    "chart_path":            {"type": (str, type(None)),           "required": False},
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
    "ai_context":            {"type": dict,                        "required": False},
    "structured_reasoning":  {"type": dict,                        "required": True},
    "llm_payload":           {"type": (dict, type(None)),          "required": False},
    "validation":            {"type": dict,                        "required": False},
    "metadata":              {"type": dict,                        "required": False},
}

# ─────────────────────────────────────────────
# TAG KEYWORDS FOR SIGNAL TAXONOMY
# ─────────────────────────────────────────────

TAG_KEYWORDS = {
    "compensation": [
        "salary", "compensation", "wage", "pay", "income",
        "bonus", "remuneration",
    ],
    "experience": [
        "experience", "tenure", "years", "seniority", "service",
    ],
    "performance": [
        "performance", "score", "rating", "evaluation",
        "assessment", "kpi",
    ],
    "demographic": [
        "age", "gender", "ethnicity", "race", "nationality",
        "location", "region", "department", "team",
    ],
    "temporal": [
        "date", "time", "year", "month", "quarter",
        "period", "fiscal",
    ],
    "satisfaction": [
        "satisfaction", "engagement", "happiness",
        "survey", "feedback", "nps",
    ],
    "education": [
        "education", "degree", "qualification",
        "certification", "diploma",
    ],
    "attendance": [
        "attendance", "absence", "leave",
        "absenteeism", "presence",
    ],
}

TAG_ACTION_MAP = {
    "compensation": {
        "action": (
            "Review compensation alignment with performance "
            "and experience metrics"
        ),
    },
    "experience": {
        "action": (
            "Optimize hiring and promotion policies based "
            "on experience impact"
        ),
    },
    "performance": {
        "action": (
            "Re-evaluate performance scoring linkage with "
            "compensation models"
        ),
    },
    "demographic": {
        "action": (
            "Analyze demographic distribution for equity "
            "and representation patterns"
        ),
    },
    "satisfaction": {
        "action": (
            "Investigate satisfaction drivers and their "
            "relationship to retention"
        ),
    },
    "education": {
        "action": (
            "Evaluate education-credential impact on outcomes"
        ),
    },
    "attendance": {
        "action": (
            "Review attendance patterns and their impact "
            "on performance"
        ),
    },
    "temporal": {
        "action": (
            "Examine temporal trends for seasonal or "
            "cyclical patterns"
        ),
    },
}

# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────

INSIGHT_SENSITIVITY = {
    "correlation": {
        "dataset_size_weight": 0.6,
        "conflict_penalty_weight": 0.7,
        "health_weight": 0.9,
    },
    "health": {
        "dataset_size_weight": 0.3,
        "conflict_penalty_weight": 0.2,
        "health_weight": 1.0,
    },
    "variability": {
        "dataset_size_weight": 0.8,
        "conflict_penalty_weight": 0.5,
        "health_weight": 0.6,
    },
}


# ─────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────

def safe_list(x):
    return list(x) if x else []


def _clean_float(value, default=0.0):
    """Convert to python float; replace NaN/Inf with default."""
    try:
        fval = float(value)
        if math.isnan(fval) or math.isinf(fval):
            return default
        return fval
    except (TypeError, ValueError):
        return default


def normalize_confidence(value):
    if value is None:
        return 0.5
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0.5
    if value > 1:
        value = value / 100
    return max(0.0, min(1.0, value))


def classify_correlation_strength(value):
    abs_value = abs(value)
    if abs_value < 0.2:
        return "negligible"
    elif abs_value < 0.4:
        return "weak"
    elif abs_value < 0.6:
        return "moderate"
    elif abs_value < 0.8:
        return "strong"
    return "very strong"


def detect_column_type(series):
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    return "categorical"


def map_priority_from_score(score):
    if score >= 0.75:
        return "high"
    elif score >= 0.45:
        return "medium"
    return "low"


def is_identifier_column(col_name, series):
    if not col_name:
        return False
    name = col_name.lower().replace("_", "").replace(" ", "")
    identifier_keywords = [
        "id", "uuid", "employeeid", "userid",
        "customerid", "serial", "serialno", "index",
    ]
    if any(keyword in name for keyword in identifier_keywords):
        return True
    if not pd.api.types.is_numeric_dtype(series):
        return False
    clean = series.dropna()
    if len(clean) < 3:
        return False
    uniqueness_ratio = clean.nunique() / len(clean)
    if uniqueness_ratio > 0.95:
        if clean.is_monotonic_increasing or clean.is_monotonic_decreasing:
            return True
        diffs = clean.diff().dropna()
        if not diffs.empty and diffs.nunique() <= 2:
            return True
    return False


def compute_unified_score(confidence, stability, significance=None, anomaly_penalty=0):
    score = 0.7 * confidence + 0.2 * stability
    if significance and isinstance(significance, str):
        if "high" in significance.lower():
            score += 0.1
        elif "not" in significance.lower():
            score -= 0.05
    score -= anomaly_penalty * 0.15
    score = max(0.15, min(1, score))
    return score


def compute_final_confidence(
    base, strength, health_score, sample_size, conflicts, anomalies
):
    try:
        score = float(base)
    except Exception:
        score = 0.5

    strength_bonus = {
        "negligible": 0.85,
        "weak": 0.92,
        "moderate": 1.0,
        "strong": 1.08,
        "very strong": 1.15,
    }
    score *= strength_bonus.get(strength, 1.0)

    if sample_size is None:
        sample_factor = 0.75
    elif sample_size < 5:
        sample_factor = 0.65
    elif sample_size < 10:
        sample_factor = 0.78
    elif sample_size < 30:
        sample_factor = 0.88
    elif sample_size < 100:
        sample_factor = 0.95
    else:
        sample_factor = 1.0
    score *= sample_factor

    try:
        normalized_health = max(0.0, min(1.0, health_score / 100))
    except Exception:
        normalized_health = 0.5
    health_factor = 0.75 + (normalized_health * 0.25)
    score *= health_factor

    conflict_count = conflicts if conflicts is not None else 0
    conflict_penalty = min(0.20, conflict_count * 0.05)
    score *= (1 - conflict_penalty)

    anomaly_count = anomalies if anomalies is not None else 0
    anomaly_penalty = min(0.15, anomaly_count * 0.03)
    score *= (1 - anomaly_penalty)

    return round(max(0.1, min(score, 0.95)), 3)


def _assign_tags(col_name):
    name = col_name.lower().replace("_", "").replace(" ", "")
    tags = []
    for tag, keywords in TAG_KEYWORDS.items():
        if any(kw in name for kw in keywords):
            tags.append(tag)
    if not tags:
        tags = ["general"]
    return tags


def _derive_theme_name(variables_list, taxonomy):
    all_tags = set()
    for v in variables_list:
        all_tags.update(taxonomy.get(v, ["general"]))
    if "compensation" in all_tags:
        return "Compensation and progression cluster"
    elif "experience" in all_tags:
        return "Experience and tenure cluster"
    elif "performance" in all_tags:
        return "Performance and score cluster"
    elif "satisfaction" in all_tags:
        return "Satisfaction and engagement cluster"
    elif "demographic" in all_tags:
        return "Demographic distribution cluster"
    elif "education" in all_tags:
        return "Education and qualification cluster"
    if len(variables_list) >= 2:
        return f"{variables_list[0]} vs {variables_list[1]}"
    elif variables_list:
        return variables_list[0]
    return "Empty cluster"


# ─────────────────────────────────────────────
# VALIDATION
# ─────────────────────────────────────────────

def validate_state(state, strict=True):
    errors = []

    if not isinstance(state, dict):
        return {"valid": False, "errors": ["State is not a dictionary"]}

    if strict:
        for key, spec in STATE_SCHEMA.items():
            if spec.get("required", False) and key not in state:
                errors.append(f"Missing required key: {key}")

        for key, spec in STATE_SCHEMA.items():
            if key in state and state[key] is not None:
                expected = spec["type"]
                if not isinstance(expected, tuple):
                    expected = (expected,)
                if not isinstance(state[key], expected):
                    errors.append(
                        f"Key '{key}' wrong type: expected "
                        f"{spec['type']}, got {type(state[key]).__name__}"
                    )

        exec_conf = state.get("executive_synthesis", {}).get("confidence")
        if exec_conf is not None:
            if not (0 <= exec_conf <= 1):
                errors.append(
                    f"Executive confidence out of range (0-1): {exec_conf}"
                )

        health_score = state.get("dataset_health", {}).get("health_score")
        if health_score is not None:
            if not (0 <= health_score <= 100):
                errors.append(
                    f"Health score out of range (0-100): {health_score}"
                )

        # analytical_stability component ranges
        stab = state.get("analytical_stability", {})
        shs = stab.get("system_health_score")
        if shs is not None and not (0 <= shs <= 100):
            errors.append(
                f"system_health_score out of range (0-100): {shs}"
            )
        scs = stab.get("signal_confidence_score")
        if scs is not None and not (0 <= scs <= 1):
            errors.append(
                f"signal_confidence_score out of range (0-1): {scs}"
            )
        si = stab.get("stability_index")
        if si is not None and not (0 <= si <= 100):
            errors.append(
                f"stability_index out of range (0-100): {si}"
            )

        raw = state.get("raw_signals", [])
        if not isinstance(raw, list):
            errors.append("raw_signals is not a list")
        else:
            for i, item in enumerate(raw[:3]):
                if not isinstance(item, dict):
                    errors.append(f"raw_signals[{i}] is not a dict")
                    break
                if "pair" not in item:
                    errors.append(f"raw_signals[{i}] missing 'pair'")
                conf = item.get("confidence")
                if conf is not None and not (0 <= conf <= 1):
                    errors.append(
                        f"raw_signals[{i}] confidence out of range: {conf}"
                    )

        pairs = state.get("correlations", {}).get("pairs")
        if pairs is not None and not isinstance(pairs, list):
            errors.append("correlations.pairs is not a list")

        exec_synth = state.get("executive_synthesis", {})
        if isinstance(exec_synth, dict) and "confidence" not in exec_synth:
            errors.append("executive_synthesis missing 'confidence' key")

        numeric_checks = [
            ("dataset_health", "health_score"),
            ("dataset_health", "completeness_score"),
            ("analytical_stability", "system_health_score"),
            ("analytical_stability", "signal_confidence_score"),
            ("analytical_stability", "stability_index"),
            ("executive_synthesis", "confidence"),
            ("executive_synthesis", "score"),
        ]
        for parent_key, child_key in numeric_checks:
            parent = state.get(parent_key, {})
            if not isinstance(parent, dict):
                continue
            val = parent.get(child_key)
            if val is None:
                continue
            try:
                fval = float(val)
                if math.isnan(fval) or math.isinf(fval):
                    errors.append(f"{parent_key}.{child_key} is NaN or Inf")
            except (TypeError, ValueError):
                errors.append(
                    f"{parent_key}.{child_key} is not numeric: {val}"
                )
    else:
        df = state.get("df")
        if df is not None and not isinstance(df, pd.DataFrame):
            errors.append("df is not a pandas DataFrame")
        file_path = state.get("file_path")
        if file_path is not None and not isinstance(file_path, str):
            errors.append("file_path is not a string")
        rows = state.get("rows")
        if rows is not None and (not isinstance(rows, int) or rows < 0):
            errors.append(f"rows must be non-negative int, got: {rows}")

    return {"valid": len(errors) == 0, "errors": errors}


# ─────────────────────────────────────────────
# NORMALIZATION LAYERS
# ─────────────────────────────────────────────

def normalize_metrics(state):
    if not state or not isinstance(state, dict):
        return state

    dh = state.get("dataset_health")
    if isinstance(dh, dict):
        for key in ("health_score", "completeness_score",
                     "anomaly_count", "dominance_issues"):
            if key in dh and dh[key] is not None:
                dh[key] = _clean_float(dh[key])
        dh["health_score"] = max(0.0, min(100.0, dh.get("health_score", 0.0)))
        dh["completeness_score"] = max(0.0, min(1.0, dh.get("completeness_score", 0.0)))
        dh["anomaly_count"] = max(0, int(dh.get("anomaly_count", 0)))
        dh["dominance_issues"] = max(0, int(dh.get("dominance_issues", 0)))

    stab = state.get("analytical_stability")
    if isinstance(stab, dict):
        for key in ("system_health_score", "stability_index"):
            if key in stab and stab[key] is not None:
                stab[key] = _clean_float(stab[key])
            stab[key] = max(0.0, min(100.0, stab.get(key, 0.0)))
        if "signal_confidence_score" in stab and stab["signal_confidence_score"] is not None:
            stab["signal_confidence_score"] = _clean_float(stab["signal_confidence_score"])
        stab["signal_confidence_score"] = max(0.0, min(1.0, stab.get("signal_confidence_score", 0.0)))

    raw = state.get("raw_signals")
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            for key in ("confidence", "score", "strength_value", "pearson"):
                if key in item and item[key] is not None:
                    item[key] = _clean_float(item[key])
            if "confidence" in item:
                item["confidence"] = max(0.0, min(1.0, item["confidence"]))
            if "pearson" in item:
                item["pearson"] = max(-1.0, min(1.0, item["pearson"]))
            if "strength_value" in item:
                item["strength_value"] = max(0.0, min(1.0, item["strength_value"]))

    es = state.get("executive_synthesis")
    if isinstance(es, dict):
        for key in ("confidence", "score"):
            if key in es and es[key] is not None:
                es[key] = _clean_float(es[key])
        es["confidence"] = max(0.0, min(1.0, es.get("confidence", 0.0)))
        es["score"] = max(0.0, min(100.0, es.get("score", 0.0)))

    corr = state.get("correlations")
    if isinstance(corr, dict):
        pairs = corr.get("pairs")
        if isinstance(pairs, list):
            for p in pairs:
                if not isinstance(p, dict):
                    continue
                for key in ("pearson", "p_value"):
                    if key in p and p[key] is not None:
                        p[key] = _clean_float(p[key])

    for key in ("rows", "columns"):
        if key in state and state[key] is not None:
            try:
                state[key] = int(state[key])
            except (TypeError, ValueError):
                state[key] = 0

    ctr = state.get("cross_theme_reasoning")
    if isinstance(ctr, dict):
        for key in ("conflict_pressure", "structural_strength"):
            if key in ctr and ctr[key] is not None:
                ctr[key] = max(0.0, min(1.0, _clean_float(ctr[key])))

    tm = state.get("theme_metrics")
    if isinstance(tm, dict):
        ob = tm.get("overall_strength_bundle")
        if isinstance(ob, dict):
            for k in ("avg_strength", "max_strength", "normalized_strength"):
                if k in ob and ob[k] is not None:
                    ob[k] = max(0.0, min(1.0, _clean_float(ob[k])))
            if "signal_count" in ob:
                ob["signal_count"] = max(0, int(ob.get("signal_count", 0)))
        for tb in tm.get("themes", []):
            if not isinstance(tb, dict):
                continue
            bundle = tb.get("signal_strength_bundle")
            if isinstance(bundle, dict):
                for k in ("avg_strength", "max_strength", "normalized_strength"):
                    if k in bundle and bundle[k] is not None:
                        bundle[k] = max(0.0, min(1.0, _clean_float(bundle[k])))
                if "signal_count" in bundle:
                    bundle["signal_count"] = max(0, int(bundle.get("signal_count", 0)))

    return state


def normalize_signals(state):
    """
    Layer 2 normalization: ensure all signal metrics are on
    consistent scales after raw computation.
    """
    if not state or not isinstance(state, dict):
        return state

    raw = state.get("raw_signals")
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            if "pearson" in item and item["pearson"] is not None:
                item["pearson"] = max(-1.0, min(1.0, _clean_float(item["pearson"])))
            if "strength_value" in item and item["strength_value"] is not None:
                item["strength_value"] = max(0.0, min(1.0, _clean_float(item["strength_value"])))
            if "score" in item and item["score"] is not None:
                item["score"] = max(0.0, min(1.0, _clean_float(item["score"])))
            if "confidence" in item and item["confidence"] is not None:
                item["confidence"] = max(0.0, min(1.0, _clean_float(item["confidence"])))
    return state


# ─────────────────────────────────────────────
# PIPELINE GUARD
# ─────────────────────────────────────────────

def pipeline_guard(state, stage_name=""):
    warnings = []
    should_stop = False

    if not isinstance(state, dict):
        return state, True, ["State is not a dictionary"]

    ranking_stages = {
        "raw_signals", "confidence_calibration",
        "deduplication", "rebalance",
    }
    if stage_name in ranking_stages:
        raw = state.get("raw_signals")
        if not raw:
            warnings.append(
                f"[{stage_name}] raw_signals is empty — "
                f"no statistical signals detected"
            )

    if stage_name == "executive_synthesis":
        es = state.get("executive_synthesis")
        if not isinstance(es, dict):
            warnings.append(
                f"[{stage_name}] executive_synthesis missing or invalid"
            )
            should_stop = True
        elif "confidence" not in es:
            warnings.append(
                f"[{stage_name}] executive_synthesis missing confidence"
            )
            should_stop = True

    stab = state.get("analytical_stability")
    if isinstance(stab, dict) and "stability_index" in stab:
        try:
            raw_val = float(stab["stability_index"])
        except (TypeError, ValueError):
            raw_val = 0.0
        if not (0 <= raw_val <= 100):
            stab["stability_index"] = max(0.0, min(100.0, raw_val))
            warnings.append(
                f"[{stage_name}] stability_index clamped to 0-100 "
                f"(was {raw_val})"
            )

    dh = state.get("dataset_health")
    if isinstance(dh, dict) and "anomaly_count" in dh:
        try:
            ac = int(dh["anomaly_count"])
        except (TypeError, ValueError):
            ac = 0
        if ac < 0:
            dh["anomaly_count"] = 0
            warnings.append(
                f"[{stage_name}] anomaly_count corrected "
                f"from {ac} to 0"
            )

    return state, should_stop, warnings


# ─────────────────────────────────────────────
# STATE INITIALIZATION
# ─────────────────────────────────────────────

def create_initial_state(df=None, file_path=None, insights_input=None):
    return {
        "df": df,
        "file_path": file_path,
        "rows": len(df) if df is not None else 0,
        "columns": len(df.columns) if df is not None else 0,
        "insights_input": insights_input or {"summary": [], "metrics": []},

        "profile": {},
        "chart_path": None,
        "correlations": {"pairs": []},
        "dataset_health": {
            "health_score": 0,
            "completeness_score": 0.0,
            "anomaly_count": 0,
            "dominance_issues": 0,
        },
        "anomaly_details": [],
        "conflicts": [],
        "raw_signals": [],
        "derived_signal_view": [],
        "signal_taxonomy": {},
        "semantic_insights": [],
        "insights": [],
        "analytical_stability": {
            "system_health_score": 0,
            "signal_confidence_score": 0.0,
            "stability_index": 0,
            "label": "unknown",
            "summary": "",
        },
        "narrative_summary": {},
        "final_insights": {
            "key_findings": [],
            "supporting_evidence": [],
            "warnings": [],
            "summary": "",
        },
        "contextual_synthesis": {},
        "theme_metrics": {"themes": [], "overall_strength_bundle": {}},
        "cross_theme_reasoning": {},
        "executive_synthesis": {},
        "recommendations": {},

        "ai_context": {},
        "structured_reasoning": {},
        "llm_payload": None,
        "validation": {},
        "metadata": {},
    }


# ─────────────────────────────────────────────
# LAYER 1: RAW COMPUTATION
# ─────────────────────────────────────────────

def generate_profile(state):
    state = state or {}
    df = state.get("df")
    profile = {}
    if df is None:
        state["profile"] = profile
        return state
    for col in df.columns:
        series = df[col]
        clean = series.dropna()
        if clean.empty:
            continue
        try:
            if pd.api.types.is_numeric_dtype(series):
                profile[col] = {
                    "type": "numeric",
                    "mean": round(float(clean.mean()), 2),
                    "median": round(float(clean.median()), 2),
                    "std": round(float(clean.std()), 2),
                    "min": float(clean.min()),
                    "max": float(clean.max()),
                }
            else:
                top_value = None
                try:
                    top_value = str(clean.value_counts().idxmax())
                except Exception:
                    pass
                profile[col] = {
                    "type": "categorical",
                    "unique_values": int(clean.nunique()),
                    "top_value": top_value,
                }
        except Exception as e:
            print(f"generate_profile skipped {col}: {e}")
    state["profile"] = profile
    return state


def generate_chart(state, column):
    state = state or {}
    df = state.get("df")
    file_path = state.get("file_path")
    state["chart_path"] = None
    if df is None or column not in df.columns:
        return state
    try:
        file_name = os.path.basename(
            file_path or "data.csv"
        ).replace(".csv", f"_{column}_chart.png")
        chart_fs_path = os.path.join("uploads", file_name)
        os.makedirs("uploads", exist_ok=True)
        plt.figure()
        df[column].dropna().hist()
        plt.title(f"{column} Distribution")
        plt.savefig(chart_fs_path)
        plt.close()
        state["chart_path"] = f"/charts/{file_name}"
    except Exception as e:
        print("generate_chart error:", e)
    return state


def generate_correlation_analysis(state):
    state = state or {}
    df = state.get("df")
    results = []
    if df is None:
        state["correlations"] = {"pairs": results}
        return state

    numeric_df = df.select_dtypes(include=[np.number]).copy()
    filtered_columns = [
        col for col in numeric_df.columns
        if not is_identifier_column(col, numeric_df[col])
    ]
    numeric_df = numeric_df[filtered_columns]

    if numeric_df.shape[1] < 2:
        state["correlations"] = {"pairs": results}
        return state

    pearson_corr = numeric_df.corr(method="pearson")
    columns = numeric_df.columns

    for col1, col2 in itertools.combinations(columns, 2):
        val = pearson_corr.loc[col1, col2]
        if pd.isna(val):
            continue
        try:
            col1_data = numeric_df[col1].dropna()
            col2_data = numeric_df[col2].dropna()
            align_idx = col1_data.index.intersection(col2_data.index)
            if len(align_idx) < 3:
                p_value = 1.0
            else:
                _, p_value = pearsonr(
                    col1_data.loc[align_idx],
                    col2_data.loc[align_idx],
                )
        except Exception:
            p_value = 1.0

        strength = classify_correlation_strength(val)
        significance = "not significant"
        if p_value < 0.01:
            significance = "highly significant"
        elif p_value < 0.05:
            significance = "significant"

        results.append({
            "pair": f"{col1} vs {col2}",
            "pearson": round(float(val), 3),
            "strength": strength,
            "p_value": round(float(p_value), 5),
            "significance": significance,
        })

    state["correlations"] = {"pairs": results}
    return state


def generate_dataset_health(state):
    state = state or {}
    df = state.get("df")
    if df is None:
        state["dataset_health"] = {
            "completeness_score": 0.0,
            "anomaly_count": 0,
            "dominance_issues": 0,
            "health_score": 0.0,
        }
        return state

    total_cells = df.shape[0] * df.shape[1]
    missing_cells = int(df.isna().sum().sum())
    completeness = 1 - (missing_cells / total_cells if total_cells > 0 else 0)

    numeric_df = df.select_dtypes(include=[np.number])
    anomaly_count = 0

    for col in numeric_df.columns:
        series = numeric_df[col].dropna()
        if series.empty:
            continue
        std = series.std()
        if std == 0:
            continue
        iqr = series.quantile(0.75) - series.quantile(0.25)
        if iqr == 0:
            continue
        spread_ratio = std / iqr
        if spread_ratio > 3:
            anomaly_count += 1

    penalty = min(25, anomaly_count * 3)
    health_score = round(
        max(0.0, min(100.0, completeness * 100 - penalty)), 2
    )

    state["dataset_health"] = {
        "completeness_score": round(completeness, 3),
        "anomaly_count": anomaly_count,
        "dominance_issues": 0,
        "health_score": health_score,
    }
    return state


def detect_anomalies(state):
    state = state or {}
    if not isinstance(state, dict):
        return state
    df = state.get("df")
    state["anomaly_details"] = []
    if df is None:
        dh = state.setdefault("dataset_health", {})
        dh["anomaly_count"] = dh.get("anomaly_count", 0)
        return state

    numeric_cols = df.select_dtypes(include=[np.number]).columns
    row_mask = pd.Series(False, index=df.index)
    details = []

    for col in numeric_cols:
        if is_identifier_column(col, df[col]):
            continue
        series = df[col].dropna()
        if len(series) < 5:
            continue
        try:
            q1 = series.quantile(0.25)
            q3 = series.quantile(0.75)
            iqr = q3 - q1
            if iqr == 0 or pd.isna(iqr):
                continue
            lower_bound = q1 - (1.5 * iqr)
            upper_bound = q3 + (1.5 * iqr)
            outlier_mask = (df[col] < lower_bound) | (df[col] > upper_bound)
            outlier_count = int(outlier_mask.sum())
            if outlier_count > 0:
                details.append({
                    "column": col,
                    "count": outlier_count,
                    "pct": round(outlier_count / max(1, len(series)), 4),
                    "lower_bound": round(float(lower_bound), 2),
                    "upper_bound": round(float(upper_bound), 2),
                })
                row_mask = row_mask | outlier_mask.fillna(False)
        except Exception as e:
            print(f"Anomaly detection error for {col}: {e}")

    total_row_anomalies = int(row_mask.sum())
    state["anomaly_details"] = details
    dh = state.setdefault("dataset_health", {})
    dh["anomaly_count"] = total_row_anomalies
    return state


def resolve_conflicts(state):
    if state is None or not isinstance(state, dict):
        return {"conflicts": []}

    conflicts = []
    df = state.get("df")
    rows = state.get("rows")
    if rows is None:
        try:
            rows = len(df) if df is not None else 0
        except Exception:
            rows = 0

    correlations = safe_list(
        (state.get("correlations") or {}).get("pairs")
    )
    dataset_health = state.get("dataset_health") or {}
    health_score = dataset_health.get(
        "health_score", dataset_health.get("health", 0)
    )
    try:
        health_score = float(health_score)
    except Exception:
        health_score = 0.0

    anomaly_details = state.get("anomaly_details") or []
    anomaly_count = dataset_health.get(
        "anomaly_count",
        len(anomaly_details) if anomaly_details else 0,
    )
    try:
        anomaly_count = int(anomaly_count)
    except Exception:
        anomaly_count = 0

    strong_relationships = [
        p for p in correlations
        if p.get("strength") in ("strong", "very strong")
    ]

    if strong_relationships:
        if health_score < 60:
            conflicts.append({
                "type": "correlation_vs_health",
                "severity": "high",
                "message": (
                    "Strong correlations exist but dataset health is low; "
                    "results may be unreliable."
                ),
                "affected_pairs": [
                    p.get("pair") for p in strong_relationships[:10]
                ],
                "health_score": health_score,
            })
        elif health_score < 80:
            conflicts.append({
                "type": "correlation_vs_health",
                "severity": "medium",
                "message": (
                    "Strong correlations detected but dataset health "
                    "is not optimal."
                ),
                "affected_pairs": [
                    p.get("pair") for p in strong_relationships[:10]
                ],
                "health_score": health_score,
            })

    if rows and rows < 10 and correlations:
        conflicts.append({
            "type": "sample_size_warning",
            "severity": "medium",
            "message": (
                f"Small dataset (n={rows}) may produce unstable "
                f"or inflated correlation estimates."
            ),
            "sample_size": rows,
        })

    if health_score > 80 and not strong_relationships:
        conflicts.append({
            "type": "signal_absence",
            "severity": "low",
            "message": (
                "Dataset quality is high but there are few strong "
                "statistical relationships."
            ),
            "health_score": health_score,
        })

    for p in strong_relationships:
        p_value = p.get("p_value", 1.0)
        try:
            pv = float(p_value)
        except Exception:
            pv = 1.0
        if pv >= 0.05:
            conflicts.append({
                "type": "strong_not_significant",
                "severity": "high",
                "message": (
                    f"Pair {p.get('pair')} shows a large effect "
                    f"({p.get('pearson')}) but is not statistically "
                    f"significant (p={pv})."
                ),
                "pair": p.get("pair"),
                "pearson": p.get("pearson"),
                "p_value": pv,
            })

    if anomaly_count > 0:
        ratio = (anomaly_count / rows) if rows else 1.0
        if ratio >= 0.10:
            sev = "high"
        elif ratio >= 0.02:
            sev = "medium"
        else:
            sev = "low"
        conflicts.append({
            "type": "anomalies_detected",
            "severity": sev,
            "message": (
                f"{anomaly_count} anomaly events detected "
                f"(~{ratio:.2%} of rows)."
            ),
            "anomaly_count": anomaly_count,
            "anomaly_ratio": round(ratio, 4),
        })

    dominance = dataset_health.get("dominance_issues", 0)
    try:
        dom_count = int(dominance)
    except Exception:
        dom_count = 0
    if dom_count > 0:
        conflicts.append({
            "type": "dominance_issues",
            "severity": "medium",
            "message": (
                f"{dom_count} column(s) appear to be dominated "
                f"by a single value."
            ),
            "dominance_issues": dom_count,
        })

    pair_names = [p.get("pair") for p in correlations if p.get("pair")]
    dup_pairs = [x for x in set(pair_names) if pair_names.count(x) > 1]
    if dup_pairs:
        conflicts.append({
            "type": "duplicate_correlation_entries",
            "severity": "low",
            "message": (
                f"Duplicate correlation entries detected for pairs: "
                f"{', '.join(dup_pairs[:10])}."
            ),
            "duplicates": dup_pairs[:20],
        })

    if df is not None:
        try:
            missing_by_col = (df.isna().mean() * 100).to_dict()
            cols_high = [
                c for c, pct in missing_by_col.items() if pct >= 50.0
            ]
            cols_med = [
                c for c, pct in missing_by_col.items()
                if 20.0 <= pct < 50.0
            ]
            if cols_high:
                conflicts.append({
                    "type": "high_missingness",
                    "severity": "high",
                    "message": (
                        f"Columns with >=50% missing values: "
                        f"{len(cols_high)}"
                    ),
                    "columns": cols_high[:20],
                    "percent_missing": {
                        c: round(missing_by_col.get(c, 0.0), 2)
                        for c in cols_high[:20]
                    },
                })
            elif cols_med:
                conflicts.append({
                    "type": "moderate_missingness",
                    "severity": "medium",
                    "message": (
                        f"Columns with 20-50% missing values: "
                        f"{len(cols_med)}"
                    ),
                    "columns": cols_med[:20],
                })
        except Exception as e:
            print("resolve_conflicts missingness check failed:", e)

    seen = set()
    unique = []
    for c in conflicts:
        key = (c.get("type"), c.get("message"))
        if key not in seen:
            seen.add(key)
            unique.append(c)

    state["conflicts"] = unique
    return state


def compute_insight_confidence(
    significance, sample_size, health_score, strength_value, conflict_count
):
    significance_score = {
        "highly significant": 0.9,
        "significant": 0.75,
        "moderate": 0.55,
        "weak": 0.35,
        "not significant": 0.2,
    }.get(significance, 0.2)

    if sample_size >= 100000:
        sample_score = 0.95
    elif sample_size >= 10000:
        sample_score = 0.85
    elif sample_size >= 1000:
        sample_score = 0.7
    elif sample_size >= 100:
        sample_score = 0.55
    else:
        sample_score = 0.4

    health_score_normalized = min(1.0, max(0.0, health_score / 100.0))
    signal_score = min(1.0, strength_value)

    confidence = (
        0.4 * significance_score
        + 0.3 * sample_score
        + 0.2 * health_score_normalized
        + 0.1 * signal_score
    )

    confidence -= min(0.15, conflict_count * 0.03)
    confidence = max(0.05, min(1.0, confidence))

    return confidence


def generate_ranked_insights(state):
    """
    Produces raw_signals: pure statistics only.
    No messages, no justifications, no confidence labels.
    """
    state = state or {}
    pairs = (state.get("correlations") or {}).get("pairs") or []
    raw = []

    sample_size = state.get("rows", 0)
    health_score = (
        (state.get("dataset_health") or {}).get("health_score", 50)
    )
    conflict_count = len(state.get("conflicts") or [])

    for item in pairs:
        strength_value = abs(item.get("pearson", 0))
        semantic_strength = item.get("strength", "weak")
        significance = item.get("significance", "not significant")
        pair_name = item.get("pair", "unknown pair")
        pearson_value = item.get("pearson", 0)

        if strength_value > 0.7:
            priority = "high"
        elif strength_value >= 0.35 and significance == "highly significant":
            priority = "medium"
        else:
            priority = "low"

        confidence = compute_insight_confidence(
            significance=significance,
            sample_size=sample_size,
            health_score=health_score,
            strength_value=strength_value,
            conflict_count=conflict_count,
        )

        raw.append({
            "type": "correlation",
            "priority": priority,
            "score": round(strength_value, 3),
            "strength": semantic_strength,
            "strength_value": strength_value,
            "pearson": pearson_value,
            "significance": significance,
            "confidence": confidence,
            "p_value": item.get("p_value"),
            "pair": pair_name,
        })

    raw.sort(key=lambda x: x.get("score", 0), reverse=True)
    state["raw_signals"] = raw[:10]
    return state


def calibrate_confidence(state):
    if not state or not isinstance(state, dict):
        return state

    insights = state.get("raw_signals") or []
    health_score = (
        (state.get("dataset_health") or {}).get("health_score", 0)
    )
    sample_size = state.get("rows", 0)
    conflict_count = len(state.get("conflicts") or [])
    anomaly_count = (
        (state.get("dataset_health") or {}).get("anomaly_count", 0)
    )

    calibrated = []
    for item in insights:
        base = item.get("confidence", 0.5)
        try:
            base = float(base)
        except Exception:
            base = 0.5

        strength = item.get("strength", "weak")
        final_conf = compute_final_confidence(
            base=base,
            strength=strength,
            health_score=health_score,
            sample_size=sample_size,
            conflicts=conflict_count,
            anomalies=anomaly_count,
        )

        item["confidence"] = round(final_conf, 3)
        item["priority"] = map_priority_from_score(final_conf)
        calibrated.append(item)

    state["raw_signals"] = calibrated
    return state


def deduplicate_insights(state):
    state = state or {}
    raw = state.get("raw_signals") or []
    seen = set()
    cleaned = []
    for item in raw:
        key = item.get("pair", "").lower().strip()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
    state["raw_signals"] = cleaned
    return state


def rebalance_scores(state):
    state = state or {}
    raw_signals = state.get("raw_signals") or []
    health = state.get("dataset_health") or {}
    conflicts = state.get("conflicts") or []

    health_score = health.get("health_score", 0)
    sample_size = state.get("rows", 0)
    size_factor = min(sample_size / 50, 1)
    conflict_factor = max(0, 1 - len(conflicts) * 0.1)
    health_factor = health_score / 100

    adjusted = []
    for item in raw_signals:
        base_score = item.get("score", 0)
        itype = item.get("type", "unknown")
        sensitivity = INSIGHT_SENSITIVITY.get(itype, {
            "dataset_size_weight": 0.5,
            "conflict_penalty_weight": 0.5,
            "health_weight": 0.5,
        })

        adjusted_score = base_score
        adjusted_score *= (
            1 - sensitivity["dataset_size_weight"]
            + sensitivity["dataset_size_weight"] * size_factor
        )
        adjusted_score *= (
            1 - sensitivity["conflict_penalty_weight"]
            + sensitivity["conflict_penalty_weight"] * conflict_factor
        )
        adjusted_score *= (
            1 - sensitivity["health_weight"]
            + sensitivity["health_weight"] * health_factor
        )

        item["score"] = round(adjusted_score, 3)
        adjusted.append(item)

    state["raw_signals"] = adjusted
    return state


# ─────────────────────────────────────────────
# LAYER 2: NORMALIZATION + TAXONOMY
# ─────────────────────────────────────────────

def generate_signal_taxonomy(state):
    """
    Assigns variable tags for semantic grouping.
    Single source of truth for tag-based logic.
    Replaces all string-matching heuristics downstream.
    """
    profile = state.get("profile", {})
    taxonomy = {}
    for col in profile:
        taxonomy[col] = _assign_tags(col)
    state["signal_taxonomy"] = taxonomy
    return state


# ─────────────────────────────────────────────
# LAYER 3: STRUCTURING
# ─────────────────────────────────────────────

def generate_contextual_synthesis(state):  
    """
    Clustering + grouping layer. NO math.
    No avg_strength, no aggregation.
    Only: variable clustering, connectivity sorting, theme naming.
    """
    raw = state.get("raw_signals") or []
    taxonomy = state.get("signal_taxonomy", {})
    threshold = CLUSTER_SIGNAL_THRESHOLD

    variable_map = defaultdict(list)

    for item in raw:
        pair = item.get("pair", "")
        if not pair or " vs " not in pair:
            continue

        v1, v2 = pair.split(" vs ")
        v1, v2 = v1.strip(), v2.strip()

        entry_data = {
            "type": "correlation",
            "strength": item.get("strength", ""),
            "value": item.get("pearson", 0),
            "pair": pair,
        }

        variable_map[v1].append({"related_to": v2, **entry_data})
        variable_map[v2].append({"related_to": v1, **entry_data})

    themes = []
    used = set()

    for var, relations in variable_map.items():
        if var in used:
            continue

        cluster_vars = {var}
        signals = []

        for r in relations:
            if abs(r.get("value", 0)) >= threshold:
                cluster_vars.add(r["related_to"])
                signals.append(r)

        for v in cluster_vars:
            used.add(v)

        if not signals:
            themes.append({
                "theme": var,
                "variables": [var],
                "supporting_signals": [],
            })
            continue

        # Connectivity for sorting (part of clustering algorithm)
        var_connectivity = {}
        for v in cluster_vars:
            rels = variable_map.get(v, [])
            var_connectivity[v] = sum(
                abs(r.get("value", 0))
                for r in rels
                if abs(r.get("value", 0)) >= threshold
            )

        variables_list = sorted(
            var_connectivity,
            key=var_connectivity.get,
            reverse=True,
        )

        # Theme naming via taxonomy tags
        theme_name = _derive_theme_name(variables_list, taxonomy)

        themes.append({
            "theme": theme_name,
            "variables": variables_list,
            "supporting_signals": signals,
        })

    cross_variable_patterns = []
    for t in themes:
        if len(t["variables"]) >= 3 and t["supporting_signals"]:
            cross_variable_patterns.append({
                "pattern": "multi-variable correlation group",
                "theme": t["theme"],
                "variables": t["variables"],
            })

    state["contextual_synthesis"] = {
        "themes": themes,
        "cross_variable_patterns": cross_variable_patterns,
    }
    return state


def generate_theme_metrics(state):
    """
    ALL strength aggregation happens here. ONCE.
    Computes signal_strength_bundle for every theme.
    Downstream layers consume bundles — no re-computation.
    """
    contextual = state.get("contextual_synthesis", {})
    themes = contextual.get("themes", [])

    theme_bundles = []
    all_strengths = []
    all_max = 0

    for theme in themes:
        signals = theme.get("supporting_signals", [])
        strengths = [abs(s.get("value", 0)) for s in signals]

        avg_strength = (
            round(sum(strengths) / len(strengths), 3) if strengths else 0
        )
        max_strength = round(max(strengths), 3) if strengths else 0
        signal_count = len(signals)
        normalized_strength = (
            round(avg_strength / 1.0, 3) if strengths else 0
        )

        bundle = {
            "avg_strength": avg_strength,
            "signal_count": signal_count,
            "max_strength": max_strength,
            "normalized_strength": normalized_strength,
        }

        theme_bundles.append({
            "theme": theme.get("theme", ""),
            "variables": theme.get("variables", []),
            "signal_strength_bundle": bundle,
        })

        all_strengths.extend(strengths)
        if max_strength > all_max:
            all_max = max_strength

    # Sort for dominant themes
    sorted_bundles = sorted(
        theme_bundles,
        key=lambda t: t["signal_strength_bundle"]["avg_strength"],
        reverse=True,
    )
    dominant = sorted_bundles[:3]

    # structural_strength: avg of dominant theme avg_strengths
    structural_strength = (
        round(
            sum(
                t["signal_strength_bundle"]["avg_strength"]
                for t in dominant
            ) / len(dominant), 3
        ) if dominant else 0
    )

    overall_bundle = {
        "avg_strength": (
            round(sum(all_strengths) / len(all_strengths), 3)
            if all_strengths else 0
        ),
        "signal_count": len(all_strengths),
        "max_strength": round(all_max, 3),
        "normalized_strength": (
            round(sum(all_strengths) / len(all_strengths), 3)
            if all_strengths else 0
        ),
    }

    state["theme_metrics"] = {
        "themes": theme_bundles,
        "dominant_themes": dominant,
        "structural_strength": structural_strength,
        "overall_strength_bundle": overall_bundle,
    }
    return state


# ─────────────────────────────────────────────
# LAYER 4: REASONING ASSEMBLY
# ─────────────────────────────────────────────

def generate_derived_signals(state):
    """
    Human-readable interpretation layer.
    Produces derived_signal_view from raw_signals.
    Messages, confidence labels, justifications live here.
    No scoring, no confidence computation.
    """
    raw = state.get("raw_signals") or []
    health = state.get("dataset_health") or {}
    conflicts = state.get("conflicts") or []

    health_score = health.get("health_score", 0)
    sample_size = state.get("rows", 0)

    derived = []
    for item in raw:
        pair_name = item.get("pair", "unknown pair")
        semantic_strength = item.get("strength", "weak")
        significance = item.get("significance", "not significant")
        pearson_value = item.get("pearson", 0)
        score = item.get("score", 0)
        confidence = item.get("confidence", 0.5)
        ctype = item.get("type", "unknown")

        # Direction
        if pearson_value > 0:
            direction = "positive"
        elif pearson_value < 0:
            direction = "negative"
        else:
            direction = "neutral"

        # Message
        if semantic_strength in ["strong", "very strong"]:
            message = (
                f"{pair_name} demonstrates a {semantic_strength} "
                f"{direction} statistical relationship"
            )
        elif semantic_strength == "moderate":
            message = (
                f"{pair_name} shows a moderate {direction} "
                f"statistical relationship"
            )
        else:
            if direction == "neutral":
                message = (
                    f"{pair_name} shows little to no "
                    f"statistical relationship"
                )
            else:
                message = (
                    f"{pair_name} shows little to no "
                    f"{direction} statistical relationship"
                )

        if significance == "not significant":
            message += (
                ", though the statistical evidence is currently limited"
            )
        elif significance == "highly significant":
            message += " with highly reliable statistical evidence"

        # Confidence label
        if confidence >= 0.85:
            confidence_label = "very high"
        elif confidence >= 0.7:
            confidence_label = "high"
        elif confidence >= 0.55:
            confidence_label = "moderate"
        elif confidence >= 0.4:
            confidence_label = "low"
        else:
            confidence_label = "very low"

        # Justification
        boosts = []
        penalties = []
        base_signal = f"{ctype} signal strength {score}"

        if score > 0.7:
            boosts.append("strong statistical signal")
        if health_score > 80:
            boosts.append("high dataset quality")
        if health_score < 60:
            penalties.append("low dataset quality")
        if sample_size < 10:
            penalties.append("small dataset size")
        if conflicts:
            penalties.append("conflicting signals detected")

        if len(penalties) == 0:
            final_reason = "Strong and reliable signal"
        elif len(penalties) == 1:
            final_reason = "Moderate reliability with minor constraints"
        else:
            final_reason = "Weak reliability due to multiple constraints"

        derived.append({
            "pair": pair_name,
            "message": message,
            "confidence_label": confidence_label,
            "justification": {
                "base_signal": base_signal,
                "boosts": boosts,
                "penalties": penalties,
                "final_reason": final_reason,
            },
        })

    state["derived_signal_view"] = derived
    return state


def generate_analytical_stability(state):
    """
    System health diagnostic.
    Three separate components:
      - system_health_score (0-100): data quality derived
      - signal_confidence_score (0-1): average signal confidence
      - stability_index (0-100): DISPLAY ONLY, no downstream logic
    """
    if not state or not isinstance(state, dict):
        return state

    try:
        dataset_health = state.get("dataset_health") or {}
        raw = state.get("raw_signals") or []
        conflicts = state.get("conflicts") or []

        health_score = float(dataset_health.get("health_score", 50))
        anomaly_count = int(dataset_health.get("anomaly_count", 0))
        sample_size = int(state.get("rows", 0))

        # Component 1: system_health_score (0-100)
        anomaly_ratio = (
            anomaly_count / sample_size if sample_size > 0 else 0
        )
        anomaly_penalty_health = min(25, anomaly_ratio * 100)
        system_health_score = round(
            max(0, min(100, health_score - anomaly_penalty_health * 0.5)), 1
        )

        # Component 2: signal_confidence_score (0-1)
        confidences = [
            float(item.get("confidence", 0.5))
            for item in raw
            if isinstance(item, dict)
        ]
        signal_confidence_score = (
            round(sum(confidences) / len(confidences), 3)
            if confidences else 0.5
        )

        # Component 3: stability_index (0-100, display only)
        if sample_size > 0:
            size_component = min(
                100.0, math.log10(sample_size + 1) * 20
            )
        else:
            size_component = 0.0

        conflict_penalty = 0.0
        for conflict in conflicts:
            severity = conflict.get("severity", "low").lower()
            if severity == "high":
                conflict_penalty += 8.0
            elif severity == "medium":
                conflict_penalty += 4.0
            else:
                conflict_penalty += 1.5
        conflict_penalty = min(15.0, conflict_penalty)

        anomaly_penalty_stab = min(15.0, anomaly_ratio * 100.0)

        health_norm = system_health_score / 100.0
        conf_norm = signal_confidence_score
        size_norm = size_component / 100.0

        raw_stability = (
            health_norm * 0.45
            + conf_norm * 0.35
            + size_norm * 0.20
        )
        penalty_fraction = (conflict_penalty + anomaly_penalty_stab) / 100.0
        raw_stability = max(0.0, min(1.0, raw_stability - penalty_fraction))
        stability_index = round(raw_stability * 100, 1)

        if stability_index >= 80:
            label = "high"
        elif stability_index >= 60:
            label = "moderate"
        elif stability_index >= 40:
            label = "guarded"
        else:
            label = "low"

        state["analytical_stability"] = {
            "system_health_score": system_health_score,
            "signal_confidence_score": signal_confidence_score,
            "stability_index": stability_index,
            "label": label,
            "summary": (
                f"stability={label} index={stability_index} "
                f"health={system_health_score} "
                f"signal_conf={signal_confidence_score} "
                f"rows={sample_size} conflicts={len(conflicts)}"
            ),
        }

    except Exception as e:
        state["analytical_stability"] = {
            "system_health_score": 0,
            "signal_confidence_score": 0.0,
            "stability_index": 0,
            "label": "unknown",
            "summary": f"stability computation failed: {str(e)}",
        }

    return state


def generate_cross_theme_reasoning(state):
    """
    Pure relationship layer.
    ONLY: sorting, pairing, overlap calculation, formatting.
    NO math. Reads all metrics from theme_metrics.
    """
    theme_metrics = state.get("theme_metrics", {})
    theme_bundles = theme_metrics.get("themes", [])
    dominant_themes = theme_metrics.get("dominant_themes", [])
    structural_strength = theme_metrics.get("structural_strength", 0)

    if not theme_bundles:
        state["cross_theme_reasoning"] = {
            "dominant_themes": [],
            "theme_interactions": [],
            "conflict_pressure": 0,
            "structural_strength": 0,
        }
        return state

    # Pairing and overlap
    interactions = []
    for i in range(len(theme_bundles)):
        for j in range(i + 1, len(theme_bundles)):
            t1, t2 = theme_bundles[i], theme_bundles[j]
            v1 = set(t1.get("variables", []))
            v2 = set(t2.get("variables", []))
            overlap = len(v1.intersection(v2))
            interaction_type = (
                "reinforcing" if overlap > 0 else "independent"
            )
            interactions.append({
                "theme_a": t1["theme"],
                "theme_b": t2["theme"],
                "interaction": interaction_type,
                "overlap_score": overlap,
            })

    total_overlap = sum(i.get("overlap_score", 0) for i in interactions)
    max_possible_overlap = len(theme_bundles) * (len(theme_bundles) - 1) / 2
    conflict_pressure = (
        round(total_overlap / max_possible_overlap, 3)
        if max_possible_overlap > 0 else 0
    )

    state["cross_theme_reasoning"] = {
        "dominant_themes": dominant_themes,
        "theme_interactions": interactions,
        "conflict_pressure": conflict_pressure,
        "structural_strength": structural_strength,
    }
    return state


def generate_structured_reasoning(state):
    """
    Pure formatting layer. NO math.
    Reads from raw_signals, theme_metrics, executive_synthesis.
    Confidence comes ONLY from executive_synthesis.confidence.
    """
    raw = state.get("raw_signals") or []
    theme_metrics = state.get("theme_metrics", {})
    executive = state.get("executive_synthesis", {})
    system_confidence = executive.get("confidence", 0.5)

    # Findings — slicing and mapping only
    findings = []
    for item in raw[:5]:
        findings.append({
            "finding": item.get("pair", ""),
            "evidence": {
                "pearson": item.get("pearson"),
                "strength": item.get("strength"),
                "significance": item.get("significance"),
            },
            "confidence": system_confidence,
            "priority": item.get("priority", "low"),
        })

    # Patterns — read from theme_metrics bundles (no computation)
    patterns = []
    for theme_bundle in theme_metrics.get("themes", [])[:5]:
        bundle = theme_bundle.get("signal_strength_bundle", {})
        patterns.append({
            "pattern": theme_bundle.get("theme", ""),
            "variables": theme_bundle.get("variables", []),
            "signal_count": bundle.get("signal_count", 0),
            "avg_strength": bundle.get("avg_strength", 0),
        })

    # Warnings — from executive risk signals only
    warnings = []
    for risk in executive.get("risk_signals", []):
        warnings.append({
            "warning": risk,
            "severity": "medium",
            "type": "executive_risk",
        })

    # Gaps
    gaps = []
    if not executive.get("key_drivers"):
        gaps.append({
            "gap": "No dominant structural drivers identified",
            "note": "Dataset may lack strong linear relationships",
        })

    nonsig = [
        r for r in raw
        if r.get("significance") == "not significant"
    ]
    if nonsig:
        gaps.append({
            "gap": (
                f"{len(nonsig)} insight(s) lack statistical "
                f"significance"
            ),
            "note": "Further validation recommended",
        })

    sparse_themes = [
        t for t in theme_metrics.get("themes", [])
        if t["signal_strength_bundle"]["signal_count"] == 0
    ]
    if sparse_themes:
        gaps.append({
            "gap": (
                f"{len(sparse_themes)} theme(s) have no "
                f"supporting signals"
            ),
            "note": "Structural grouping may be incomplete",
        })

    state["structured_reasoning"] = {
        "findings": findings,
        "patterns": patterns,
        "warnings": warnings,
        "gaps": gaps,
    }
    return state


# ─────────────────────────────────────────────
# LAYER 5: DECISION LAYER
# ─────────────────────────────────────────────

def generate_executive_synthesis(state):
    """
    ┌──────────────────────────────────────────────────────────────┐
    │  SINGLE AUTHORITATIVE INTERPRETATION LAYER                  │
    │                                                              │
    │  executive_synthesis.confidence is the CANONICAL value.     │
    │  Uses system_health_score and signal_confidence_score       │
    │  directly — NOT stability_index (display only).             │
    │                                                              │
    │  Consumes: raw_signals, cross_theme_reasoning,              │
    │  theme_metrics, analytical_stability.                       │
    │  NEVER returns empty. ALWAYS produces complete output.      │
    └──────────────────────────────────────────────────────────────┘
    """
    cross_theme = state.get("cross_theme_reasoning", {})
    stability = state.get("analytical_stability", {})
    raw = state.get("raw_signals", [])
    theme_metrics = state.get("theme_metrics", {})

    dominant_themes = cross_theme.get("dominant_themes", [])
    conflict_pressure = cross_theme.get("conflict_pressure", 0)

    system_health_score = stability.get("system_health_score", 50)
    signal_confidence_score = stability.get("signal_confidence_score", 0.5)
    stability_label = stability.get("label", "unknown")

    # ── Key drivers ──
    key_drivers = [
        t.get("theme") for t in dominant_themes[:3] if t.get("theme")
    ]

    # ── Key drivers metadata (read bundles, no computation) ──
    key_drivers_meta = []
    for t in dominant_themes[:3]:
        if not t.get("theme"):
            continue
        bundle = t.get("signal_strength_bundle", {})
        key_drivers_meta.append({
            "name": t["theme"],
            "signal_strength_bundle": bundle,
            "variables": t.get("variables", []),
        })

    # ── Risk signals ──
    risk_signals = []

    if system_health_score < 60:
        risk_signals.append(
            "Low analytical stability indicates reduced confidence "
            "in structural patterns"
        )

    if conflict_pressure > 0.3:
        risk_signals.append(
            "Structural overlap between themes suggests potential "
            "conflicting signals"
        )

    if not dominant_themes:
        risk_signals.append(
            "No dominant structural themes identified in the dataset"
        )

    weak_themes = [
        t for t in dominant_themes
        if t.get("signal_strength_bundle", {}).get("avg_strength", 0)
        < WEAK_SIGNAL_FILTER
    ]
    if weak_themes:
        risk_signals.append(
            "Some dominant patterns show weak structural signals"
        )

    # ── Opportunity signals (read from bundles) ──
    opportunity_signals = []
    for t in dominant_themes[:3]:
        bundle = t.get("signal_strength_bundle", {})
        avg = bundle.get("avg_strength", 0)
        if avg > 0.4:
            opportunity_signals.append(
                f"Structural relationship observed in "
                f"{t.get('theme')} "
                f"(avg strength: {avg:.2f})"
            )

    # ── Decision frame ──
    if system_health_score > 75 and opportunity_signals:
        decision_frame = (
            "Dataset shows reliable structural patterns suitable "
            "for strategic interpretation"
        )
    elif system_health_score > 50:
        decision_frame = (
            "Dataset shows moderate reliability; insights should "
            "be used with contextual caution"
        )
    else:
        decision_frame = (
            "Dataset shows unstable patterns; interpretations "
            "should be treated as exploratory"
        )

    # ── Executive summary (always produced) ──
    summary_parts = []
    if key_drivers:
        summary_parts.append(
            "Primary structural drivers: " + ", ".join(key_drivers)
        )
    else:
        summary_parts.append(
            "No dominant structural drivers identified"
        )

    if opportunity_signals:
        summary_parts.append(
            "Key opportunities: " + "; ".join(opportunity_signals)
        )
    if risk_signals:
        summary_parts.append(
            "Key risks: " + "; ".join(risk_signals)
        )

    executive_summary = ". ".join(summary_parts)

    # ── CANONICAL CONFIDENCE ──
    ranked_confidences = [
        i.get("confidence", 0.5)
        for i in raw
        if isinstance(i, dict)
    ]

    insight_confidence = (
        sum(ranked_confidences) / len(ranked_confidences)
        if ranked_confidences else 0.5
    )

    health_norm = max(0, min(system_health_score, 100)) / 100

    conflict_penalty = min(0.15, conflict_pressure * 0.15)

    final_confidence = (
        (0.7 * insight_confidence + 0.3 * health_norm)
        * (1 - conflict_penalty)
    )
    final_confidence = max(0.1, min(final_confidence, 0.99))

    state["executive_synthesis"] = {
        "executive_summary": executive_summary,
        "decision_frame": decision_frame,
        "key_drivers": key_drivers,
        "key_drivers_meta": key_drivers_meta,
        "risk_signals": risk_signals,
        "opportunity_signals": opportunity_signals,
        "confidence": round(final_confidence, 3),
        "score": round(final_confidence * 100, 2),
        "stability_label": stability_label,
    }

    return state


# ─────────────────────────────────────────────
# LAYER 6: OUTPUT LAYER
# ─────────────────────────────────────────────

def generate_semantic_insights(correlations, df=None):
    if not correlations or "top_correlations" not in correlations:
        return []
    insights = []
    for item in correlations["top_correlations"]:
        pair = item["pair"]
        value = item["pearson"]
        abs_val = abs(value)
        if abs_val >= 0.85:
            strength = "very strong"
        elif abs_val >= 0.6:
            strength = "strong"
        elif abs_val >= 0.3:
            strength = "moderate"
        else:
            continue
        direction = "positive" if value > 0 else "negative"
        col1, col2 = pair.split(" vs ")
        if "salary" in pair.lower():
            meaning = (
                "indicates compensation is closely tied to "
                "performance or experience patterns"
            )
        elif "experience" in pair.lower():
            meaning = (
                "suggests career progression strongly "
                "influences this relationship"
            )
        elif "performance" in pair.lower():
            meaning = (
                "suggests performance scoring aligns with "
                "other business metrics"
            )
        else:
            meaning = "shows structural dependency between variables"
        insights.append(
            f"{col1} and {col2} show a {strength} {direction} "
            f"relationship, {meaning}"
        )
    return insights


def add_semantic_insights_to_state(state):
    correlations = (state.get("correlations") or {}).get("pairs", [])
    input_corr = {"top_correlations": []}
    for p in correlations:
        input_corr["top_correlations"].append({
            "pair": p.get("pair"),
            "pearson": p.get("pearson"),
        })
    semantic = generate_semantic_insights(input_corr, state.get("df"))
    state["semantic_insights"] = semantic
    state["insights"] = semantic
    return state


def generate_narrative_summary(state):
    """
    Passive reflection layer.
    Uses stability_index for display only.
    No 'should/implies/guide' language. Factual restatement only.
    """
    executive = state.get("executive_synthesis", {})
    stability = state.get("analytical_stability", {})
    health = state.get("dataset_health", {})

    if state.get("rows", 0) == 0:
        return {
            "full_narrative": (
                "No dataset available for narrative generation."
            )
        }

    health_score = health.get("health_score", 0)
    quality_assessment = {
        "assessment": f"Dataset quality score is {health_score}/100.",
        "evidence": {"health_score": health_score},
        "note": "Dataset completeness and cleanliness metric.",
    }

    key_drivers = executive.get("key_drivers", [])
    correlation_assessment = {
        "assessment": (
            f"Primary structural drivers: {', '.join(key_drivers)}."
            if key_drivers
            else "No dominant structural drivers identified."
        ),
        "evidence": {"key_drivers": key_drivers},
        "note": "Grouped structural relationships.",
    }

    anomaly_count = health.get("anomaly_count", 0)
    anomaly_assessment = {
        "assessment": f"Detected {anomaly_count} anomaly events.",
        "evidence": {"anomaly_count": anomaly_count},
        "note": "Dataset variability indicators.",
    }

    # Display-only: stability_index
    stab_index = stability.get("stability_index", 0)
    stab_label = executive.get("stability_label", "unknown")
    reliability_assessment = {
        "assessment": (
            f"Analytical stability is {stab_label} "
            f"(index: {stab_index})."
        ),
        "evidence": {"stability_index": stab_index, "label": stab_label},
        "note": "Consistency metric for analytical outputs.",
    }

    risks = executive.get("risk_signals", [])
    opps = executive.get("opportunity_signals", [])
    structure_assessment = {
        "assessment": (
            f"Identified {len(risks)} risk signals and "
            f"{len(opps)} opportunity signals."
        ),
        "evidence": {"risks": len(risks), "opportunities": len(opps)},
        "note": "Signals from executive layer.",
    }

    full_narrative = " ".join([
        quality_assessment["assessment"],
        correlation_assessment["assessment"],
        anomaly_assessment["assessment"],
        reliability_assessment["assessment"],
        structure_assessment["assessment"],
    ])

    return {
        "quality_assessment": quality_assessment,
        "correlation_assessment": correlation_assessment,
        "anomaly_assessment": anomaly_assessment,
        "reliability_assessment": reliability_assessment,
        "structure_assessment": structure_assessment,
        "full_narrative": full_narrative,
    }


def generate_final_insights(state):
    """
    Pure presentation layer.
    Consumes ONLY executive_synthesis.
    """
    executive_synthesis = state.get("executive_synthesis", {})

    state["final_insights"] = {
        "key_findings": executive_synthesis.get("key_drivers", [])[:5],
        "supporting_evidence": (
            executive_synthesis.get("opportunity_signals", [])[:5]
        ),
        "warnings": executive_synthesis.get("risk_signals", [])[:5],
        "summary": executive_synthesis.get("executive_summary", ""),
    }
    return state


def align_contradictions(state):
    """
    Consistency safety net.
    Ensures narrative wording does not overclaim relative to
    statistical evidence.
    """
    correlations = state.get("correlations", {})
    correlation_pairs = correlations.get("pairs", [])
    if not correlation_pairs:
        return state

    hierarchy = [
        "negligible", "weak", "moderate", "strong", "very strong"
    ]
    strongest_detected = "negligible"
    for pair in correlation_pairs:
        strength = pair.get("strength", "negligible")
        if (
            strength in hierarchy
            and hierarchy.index(strength)
            > hierarchy.index(strongest_detected)
        ):
            strongest_detected = strength

    narrative = state.get("narrative_summary", {})

    if isinstance(narrative, dict) and "full_narrative" in narrative:
        text = narrative["full_narrative"]
        if strongest_detected in ["negligible", "weak"]:
            text = re.sub(r"\bvery strong\b", "weak", text)
            text = re.sub(r"\bstrong\b", "weak", text)
            text = re.sub(r"\bmoderate\b", "weak", text)
        elif strongest_detected == "moderate":
            text = re.sub(r"\bvery strong\b", "moderate", text)
            text = re.sub(r"\bstrong\b", "moderate", text)
        elif strongest_detected == "strong":
            text = re.sub(r"\bvery strong\b", "strong", text)
        narrative["full_narrative"] = text
        state["narrative_summary"] = narrative

    return state


def generate_recommendations(state):
    """
    Action layer. Tag-based only. No string heuristics.
    Consumes: executive_synthesis, theme_metrics, signal_taxonomy.
    Confidence inherited from executive_synthesis — no recomputation.
    """
    executive = state.get("executive_synthesis", {})
    theme_metrics = state.get("theme_metrics", {})
    taxonomy = state.get("signal_taxonomy", {})

    recommendations = []
    key_drivers_meta = executive.get("key_drivers_meta", [])
    system_confidence = executive.get("confidence", 0.3)

    for driver_meta in key_drivers_meta:
        bundle = driver_meta.get("signal_strength_bundle", {})
        avg_strength = bundle.get("avg_strength", 0)

        if avg_strength < 0.3:
            continue

        priority = (
            "high" if avg_strength > 0.6
            else ("medium" if avg_strength > 0.3 else "low")
        )

        name = driver_meta["name"]
        signal_count = bundle.get("signal_count", 0)
        variables = driver_meta.get("variables", [])

        # Collect tags from taxonomy — NO string matching
        all_tags = set()
        for v in variables:
            tags = taxonomy.get(v, ["general"])
            all_tags.update(tags)

        # Find matching action via tags
        action_found = False
        for tag in all_tags:
            if tag in TAG_ACTION_MAP and tag != "general":
                recommendations.append({
                    "action": TAG_ACTION_MAP[tag]["action"],
                    "reason": (
                        f"Structural cluster '{name}' shows "
                        f"{signal_count} supporting signals "
                        f"(avg strength: {avg_strength:.2f})"
                    ),
                    "priority": priority,
                    "confidence": round(system_confidence, 3),
                    "tags": sorted(all_tags),
                })
                action_found = True
                break

        if not action_found:
            top_vars = variables[:3]
            recommendations.append({
                "action": (
                    f"Investigate structural relationship between "
                    f"{', '.join(top_vars)}"
                ),
                "reason": (
                    f"Structural cluster '{name}' shows "
                    f"{signal_count} supporting signals "
                    f"(avg strength: {avg_strength:.2f})"
                ),
                "priority": priority,
                "confidence": round(system_confidence, 3),
                "tags": sorted(all_tags),
            })

    if system_confidence < 0.5:
        recommendations.append({
            "action": (
                "Avoid high-stakes decisions without further "
                "data validation"
            ),
            "reason": (
                "Low system confidence reduces reliability of "
                "derived insights"
            ),
            "priority": "low",
            "confidence": round(system_confidence, 3),
            "tags": [],
        })

    seen = set()
    unique = []
    for r in recommendations:
        if r["action"] not in seen:
            unique.append(r)
            seen.add(r["action"])

    state["recommendations"] = {
        "recommendations": unique,
        "total_recommendations": len(unique),
        "system_confidence": round(system_confidence, 3),
    }
    return state


# ─────────────────────────────────────────────
# AI-READY LAYERS
# ─────────────────────────────────────────────

def build_ai_context(state):
    """
    Converts pipeline state into a prompt-ready JSON structure.
    Merges raw_signals and derived_signal_view for consumers.
    """
    profile = state.get("profile", {})
    correlations = state.get("correlations", {})
    health = state.get("dataset_health", {})
    anomalies = state.get("anomaly_details", [])
    conflicts = state.get("conflicts", [])
    raw = state.get("raw_signals", [])
    derived = state.get("derived_signal_view", [])
    stability = state.get("analytical_stability", {})
    narrative = state.get("narrative_summary", {})
    synthesis = state.get("contextual_synthesis", {})
    executive = state.get("executive_synthesis", {})
    theme_metrics = state.get("theme_metrics", {})

    numeric_count = sum(
        1 for v in profile.values() if v.get("type") == "numeric"
    )
    categorical_count = sum(
        1 for v in profile.values() if v.get("type") == "categorical"
    )

    dataset_overview = {
        "rows": state.get("rows", 0),
        "columns": state.get("columns", 0),
        "numeric_features": numeric_count,
        "categorical_features": categorical_count,
        "health_score": health.get("health_score", 0),
        "completeness_score": health.get("completeness_score", 0),
        "anomaly_count": health.get("anomaly_count", 0),
    }

    pairs = correlations.get("pairs", [])
    statistical_signals = [
        {
            "pair": p.get("pair"),
            "pearson": p.get("pearson"),
            "strength": p.get("strength"),
            "p_value": p.get("p_value"),
            "significance": p.get("significance"),
        }
        for p in sorted(
            pairs, key=lambda x: -abs(x.get("pearson", 0))
        )[:10]
    ]

    quality_signals = {
        "health_score": health.get("health_score", 0),
        "conflicts": [
            {
                "type": c.get("type"),
                "severity": c.get("severity"),
                "message": c.get("message"),
            }
            for c in conflicts[:10]
        ],
        "anomaly_summary": {
            "total_anomalies": health.get("anomaly_count", 0),
            "details": [
                {
                    "column": a.get("column"),
                    "count": a.get("count"),
                    "pct": a.get("pct"),
                }
                for a in anomalies[:10]
            ],
        },
    }

    # Merge raw_signals + derived_signal_view
    derived_map = {
        d.get("pair", ""): d
        for d in derived
        if isinstance(d, dict)
    }
    confidence_map = []
    for item in raw[:10]:
        pair = item.get("pair", "")
        d = derived_map.get(pair, {})
        confidence_map.append({
            "pair": pair,
            "message": d.get("message", ""),
            "confidence": item.get("confidence"),
            "priority": item.get("priority"),
            "strength": item.get("strength"),
            "justification": d.get("justification", {}),
        })

    stability_signal = {
        "system_health_score": stability.get("system_health_score"),
        "signal_confidence_score": stability.get("signal_confidence_score"),
        "stability_index": stability.get("stability_index"),
        "label": stability.get("label"),
    }

    thematic_structure = {
        "themes": [
            {
                "theme": t.get("theme"),
                "variables": t.get("variables"),
                "signal_strength_bundle": t.get("signal_strength_bundle", {}),
            }
            for t in theme_metrics.get("themes", [])[:5]
        ],
        "cross_patterns": synthesis.get("cross_variable_patterns", [])[:3],
    }

    executive_signals = {
        "key_drivers": executive.get("key_drivers", []),
        "key_drivers_meta": executive.get("key_drivers_meta", []),
        "risk_signals": executive.get("risk_signals", []),
        "opportunity_signals": executive.get("opportunity_signals", []),
        "decision_frame": executive.get("decision_frame", ""),
        "confidence": executive.get("confidence", 0),
    }

    return {
        "dataset_overview": dataset_overview,
        "statistical_signals": statistical_signals,
        "quality_signals": quality_signals,
        "confidence_map": confidence_map,
        "stability": stability_signal,
        "thematic_structure": thematic_structure,
        "executive_signals": executive_signals,
        "narrative_blocks": (
            narrative
            if isinstance(narrative, dict)
            else {"full_narrative": str(narrative)}
        ),
    }


def build_llm_payload(state):
    """
    Final API contract builder.
    PURE SERIALIZER ONLY — no transformations, no logic, no computation.
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "context": state.get("ai_context", {}),
        "structured_reasoning": state.get("structured_reasoning", {}),
        "recommendations": state.get("recommendations", {}),
        "stability": state.get("analytical_stability", {}),
        "health": state.get("dataset_health", {}),
    }


# ─────────────────────────────────────────────
# MAIN PIPELINE ENTRY POINT
# ─────────────────────────────────────────────

def analyze_data(file_path):
    df = pd.read_csv(file_path)
    state = create_initial_state(df=df, file_path=file_path)

    start_time = time.time()
    layers_executed = []
    layers_failed = []
    guard_warnings_all = []

    # ── Pre-execution validation ──
    pre_check = validate_state(state, strict=False)
    if not pre_check["valid"]:
        return {
            "error": "Pre-execution validation failed",
            "errors": pre_check["errors"],
            "metadata": {
                "pipeline_version": PIPELINE_VERSION,
                "schema_version": SCHEMA_VERSION,
                "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

    # ── Initial normalization ──
    state = normalize_metrics(state)

    # ── Helper ──
    def _run_layer(name, fn, *args, **kwargs):
        nonlocal state
        try:
            state = fn(state, *args, **kwargs) if args or kwargs else fn(state)
            layers_executed.append(name)
            state = normalize_metrics(state)
            state, should_stop, warnings = pipeline_guard(state, name)
            guard_warnings_all.extend(warnings)
            if should_stop:
                raise RuntimeError(
                    f"Pipeline guard STOP at '{name}': "
                    f"{'; '.join(warnings)}"
                )
        except RuntimeError:
            raise
        except Exception as e:
            layers_failed.append({"layer": name, "error": str(e)})
            print(f"[pipeline] {name} failed: {e}")

    # ══════════════════════════════════════════
    # LAYER 1: RAW COMPUTATION
    # ══════════════════════════════════════════

    _run_layer("profile", generate_profile)

    # Chart
    try:
        num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        filtered_cols = [
            col for col in num_cols
            if not is_identifier_column(col, df[col])
        ]
        chart_col = None
        if filtered_cols:
            variance_map = {col: df[col].std() for col in filtered_cols}
            sorted_cols = sorted(
                variance_map.items(), key=lambda x: x[1], reverse=True
            )
            chart_col = sorted_cols[0][0]
        elif num_cols:
            chart_col = num_cols[0]
        elif len(df.columns):
            chart_col = df.columns[0]
        if chart_col:
            _run_layer("chart", lambda s: generate_chart(s, chart_col))
        else:
            layers_executed.append("chart")
    except RuntimeError:
        raise
    except Exception as e:
        layers_failed.append({"layer": "chart", "error": str(e)})
        print(f"[pipeline] chart failed: {e}")

    _run_layer("correlations", generate_correlation_analysis)
    _run_layer("dataset_health", generate_dataset_health)
    _run_layer("anomalies", detect_anomalies)
    _run_layer("conflicts", resolve_conflicts)
    _run_layer("raw_signals", generate_ranked_insights)
    _run_layer("confidence_calibration", calibrate_confidence)
    _run_layer("deduplication", deduplicate_insights)
    _run_layer("rebalance", rebalance_scores)

    # ══════════════════════════════════════════
    # LAYER 2: NORMALIZATION + TAXONOMY
    # ══════════════════════════════════════════

    _run_layer("normalize_signals", normalize_signals)
    _run_layer("signal_taxonomy", generate_signal_taxonomy)

    # ══════════════════════════════════════════
    # LAYER 3: STRUCTURING
    # ══════════════════════════════════════════

    _run_layer("contextual_synthesis", generate_contextual_synthesis)
    _run_layer("theme_metrics", generate_theme_metrics)

    # ══════════════════════════════════════════
    # LAYER 4: REASONING ASSEMBLY
    # ══════════════════════════════════════════

    _run_layer("derived_signals", generate_derived_signals)
    _run_layer("analytical_stability", generate_analytical_stability)
    _run_layer("cross_theme_reasoning", generate_cross_theme_reasoning)
    _run_layer("structured_reasoning", generate_structured_reasoning)

    # ══════════════════════════════════════════
    # LAYER 5: DECISION LAYER
    # ══════════════════════════════════════════

    _run_layer("executive_synthesis", generate_executive_synthesis)

    # ══════════════════════════════════════════
    # LAYER 6: OUTPUT LAYER
    # ══════════════════════════════════════════

    _run_layer("semantic_insights", add_semantic_insights_to_state)

    def _narrative(s):
        s["narrative_summary"] = generate_narrative_summary(s)
        return s

    _run_layer("narrative_summary", _narrative)
    _run_layer("final_insights", generate_final_insights)
    _run_layer("alignment", align_contradictions)
    _run_layer("recommendations", generate_recommendations)

    def _ai_context(s):
        s["ai_context"] = build_ai_context(s)
        return s

    _run_layer("ai_context", _ai_context)

    def _llm_payload(s):
        s["llm_payload"] = build_llm_payload(s)
        return s

    _run_layer("llm_payload", _llm_payload)

    # ── Post-execution validation ──
    state["validation"] = validate_state(state, strict=True)

    # ── Metadata ──
    elapsed_ms = round((time.time() - start_time) * 1000, 2)

    state["metadata"] = {
        "pipeline_version": PIPELINE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
        "execution_duration_ms": elapsed_ms,
        "layers_executed": layers_executed,
        "layers_failed": layers_failed,
        "layers_total": len(layers_executed) + len(layers_failed),
        "layers_success_count": len(layers_executed),
        "layers_failure_count": len(layers_failed),
        "guard_warnings": guard_warnings_all,
        "dataset_shape": {
            "rows": len(df),
            "columns": len(df.columns),
        },
    }

    return state