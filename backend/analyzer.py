import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import itertools
import re
from scipy.stats import pearsonr
from collections import defaultdict

INSIGHT_SENSITIVITY = {
    "correlation": {
        "dataset_size_weight": 0.6,
        "conflict_penalty_weight": 0.7,
        "health_weight": 0.9
    },
    "health": {
        "dataset_size_weight": 0.3,
        "conflict_penalty_weight": 0.2,
        "health_weight": 1.0
    },
    "variability": {
        "dataset_size_weight": 0.8,
        "conflict_penalty_weight": 0.5,
        "health_weight": 0.6
    }
}

def generate_semantic_insights(correlations, df=None):
    if not correlations or "top_correlations" not in correlations:
        return []

    insights = []

    for item in correlations["top_correlations"]:
        pair = item["pair"]
        value = item["pearson"]

        abs_val = abs(value)

        # strength classification
        if abs_val >= 0.85:
            strength = "very strong"
        elif abs_val >= 0.6:
            strength = "strong"
        elif abs_val >= 0.3:
            strength = "moderate"
        else:
            continue  # filter weak relationships (Step 4.5 pre-applied lightly)

        direction = "positive" if value > 0 else "negative"

        col1, col2 = pair.split(" vs ")

        # contextual interpretation
        if "salary" in pair.lower():
            meaning = "indicates compensation is closely tied to performance or experience patterns"
        elif "experience" in pair.lower():
            meaning = "suggests career progression strongly influences this relationship"
        elif "performance" in pair.lower():
            meaning = "suggests performance scoring aligns with other business metrics"
        else:
            meaning = "shows structural dependency between variables"

        insights.append(
            f"{col1} and {col2} show a {strength} {direction} relationship, {meaning}"
        )

    return insights

def add_semantic_insights_to_state(state):
    correlations = (state.get("correlations") or {}).get("pairs", [])
    # The original function expects a dict with "top_correlations" (older) or can be adapted:
    # We'll create a miniature structure for compatibility:
    input_corr = {"top_correlations": []}
    for p in correlations:
        input_corr["top_correlations"].append({
            "pair": p.get("pair"),
            "pearson": p.get("pearson")
        })

    semantic = generate_semantic_insights(input_corr, state.get("df"))
    state["semantic_insights"] = semantic
    # Also write a user-facing 'insights' key that main.py expects
    state["insights"] = semantic
    return state

def detect_column_type(series):
        if pd.api.types.is_numeric_dtype(series):
            return "numeric"
        return "categorical"    

def profile_numeric_column(series):
        return {
            "type": "numeric",
            "mean": float(series.mean()),
            "median": float(series.median()),
            "std": float(series.std()),
            "min": float(series.min()),
            "max": float(series.max())
        }    

def profile_categorical_column(series):
        mode = series.mode()
        top_value = mode.iloc[0] if not mode.empty else None

        return {
            "type": "categorical",
            "unique_values": int(series.nunique()),
            "top_value": top_value
        }    

def generate_narrative_summary(df, correlations, health):

    if df is None or len(df) == 0:
        return "No dataset available for narrative generation."

    numeric_cols = df.select_dtypes(include=["number"]).columns
    categorical_cols = df.select_dtypes(exclude=["number"]).columns

    summary_parts = []

    sample_size = len(df)
    print("NARRATIVE SAMPLE SIZE:", sample_size)
    correlation_pairs = correlations.get("pairs", [])

    health_score = (
        health.get("health_score")
        or health.get("completeness_score")
        or 0
    )

    anomaly_count = health.get("anomaly_count", 0)

    # ------------------------------------------------
    # Dataset quality interpretation
    # ------------------------------------------------

    if health_score >= 90:

        summary_parts.append(
            "The dataset demonstrates strong structural quality with high completeness and minimal integrity concerns."
        )

    elif health_score >= 70:

        summary_parts.append(
            "The dataset is generally reliable, although some structural inconsistencies may affect analytical precision."
        )

    else:

        summary_parts.append(
            "The dataset contains substantial quality limitations that may reduce analytical reliability."
        )

    # ------------------------------------------------
    # Correlation interpretation
    # ------------------------------------------------

    strong_pairs = [
        pair for pair in correlation_pairs
        if pair.get("strength") in ["strong", "very strong"]
    ]

    moderate_pairs = [
        pair for pair in correlation_pairs
        if pair.get("strength") == "moderate"
    ]

    if strong_pairs:

        top_pair = max(
            strong_pairs,
            key=lambda x: abs(x.get("pearson", 0))
        )

        pair_name = top_pair["pair"]

        corr_value = top_pair["pearson"]

        direction = (
            "positive"
            if corr_value >= 0
            else "negative"
        )

        summary_parts.append(
            f"The strongest analytical relationship identified was a {direction} association between {pair_name}."
        )

        if len(strong_pairs) >= 3:

            summary_parts.append(
                "Several variables exhibit tightly aligned statistical behavior, suggesting consistent structural patterns across the dataset."
            )

    elif moderate_pairs:

        top_pair = max(
            moderate_pairs,
            key=lambda x: abs(x.get("pearson", 0))
        )

        pair_name = top_pair["pair"]

        direction = (
            "positive"
            if top_pair.get("pearson", 0) >= 0
            else "negative"
        )

        summary_parts.append(
            f"A moderate {direction} relationship was detected between {pair_name}."
        )

    else:

        summary_parts.append(
            "Most observed statistical relationships were weak, indicating limited linear dependency between variables."
        )

    # ------------------------------------------------
    # Anomaly interpretation
    # ------------------------------------------------

    if anomaly_count > 0:

        anomaly_pct = round(
            (anomaly_count / max(sample_size, 1)) * 100,
            2
        )

        if anomaly_pct < 2:

            summary_parts.append(
                f"A small number of statistical outliers were detected ({anomaly_pct}% of records), though overall distribution behavior remains stable."
            )

        else:

            summary_parts.append(
                f"The dataset contains a noticeable concentration of outliers ({anomaly_pct}% of records), which may influence aggregate statistical interpretations."
            )

    # ------------------------------------------------
    # Reliability interpretation
    # ------------------------------------------------

    if sample_size < 10:

        summary_parts.append(
            "Findings should be interpreted cautiously due to limited sample size."
        )

    elif sample_size >= 1000 and health_score >= 80:

        summary_parts.append(
            "The dataset size is sufficiently large to support relatively stable analytical inference."
        )

    # ------------------------------------------------
    # Dataset structure
    # ------------------------------------------------

    summary_parts.append(
        f"The dataset includes {len(numeric_cols)} numeric features and {len(categorical_cols)} categorical features."
    )

    return " ".join(summary_parts)

def generate_conflict_detection(correlations, health, df):
    conflicts = []

    health_score = health.get("health_score", 0)

    # 1. High correlation but low dataset quality
    correlation_pairs = correlations.get("pairs", [])

    strong_relationships = [
        pair for pair in correlation_pairs
        if pair.get("strength") in ["strong", "very strong"]
    ]

    if strong_relationships:

        if health_score < 60:
            conflicts.append({
                "type": "correlation_vs_health",
                "severity": "high",
                "message": "Strong correlations exist but dataset quality is low, results may be unreliable"
            })

        elif health_score < 80:
            conflicts.append({
                "type": "correlation_vs_health",
                "severity": "medium",
                "message": "Strong correlations detected but dataset quality is not optimal"
            })

    # 2. Small dataset warning
    if len(df) < 10 and correlations.get("top_correlations"):
        conflicts.append({
            "type": "sample_size_warning",
            "severity": "medium",
            "message": "Small dataset size may inflate correlation strength"
        })

    # 3. No correlations but good health
    if health_score > 80 and not strong_relationships:
        conflicts.append({
            "type": "signal_absence",
            "severity": "low",
            "message": "High-quality dataset with moderate but limited statistical relationships"
        })

    return conflicts

def generate_analytical_stability(state):
    """
    Populate state['analytical_stability'] with:
      - score (0..100)
      - confidence (0..1, mean of calibrated confidences)
      - label ('high'|'medium'|'low')
      - summary (short string)
    """
    if not state or not isinstance(state, dict):
        return state

    health_score = (state.get("dataset_health") or {}).get("health_score", 50) or 50
    sample_size = state.get("rows", 0)
    size_factor = min(1.0, (sample_size or 0) / 1000.0)

    ranked = state.get("ranked_insights") or []
    confidences = [float(i.get("confidence", 0.5)) for i in ranked] if ranked else []
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.5

    conflict_count = len(state.get("conflicts") or [])
    anomaly_count = (state.get("dataset_health") or {}).get("anomaly_count", 0) or len(state.get("anomaly_details") or [])

    # Baseline weighted aggregation
    baseline = 0.6 * float(health_score) + 0.3 * (avg_conf * 100.0) + 0.1 * (size_factor * 100.0)

    # Penalties
    penalty_conflicts = min(30.0, conflict_count * 5.0)
    penalty_anomalies = min(15.0, anomaly_count * 2.0)

    score = baseline - (penalty_conflicts + penalty_anomalies)
    score = max(0.0, min(100.0, score))

    if score >= 75:
        label = "high"
    elif score >= 50:
        label = "medium"
    else:
        label = "low"

    summary = f"Analytical stability is {label} (score={score:.1f}). Based on health={health_score}, avg_conf={avg_conf:.2f}, n={sample_size}."

    state["analytical_stability"] = {
        "score": round(score, 1),
        "confidence": round(avg_conf, 3),
        "label": label,
        "summary": summary
    }
    return state

def rebalance_scores(ranked_insights, health, conflicts, df):
    adjusted = []

    health_score = health.get("health_score", 0)
    sample_size = len(df)

    size_factor = min(sample_size / 50, 1)
    conflict_factor = max(0, 1 - len(conflicts) * 0.1)
    health_factor = health_score / 100

    for item in ranked_insights:
        base_score = item.get("score", 0)
        itype = item.get("type", "unknown")

        sensitivity = INSIGHT_SENSITIVITY.get(
            itype,
            {
                "dataset_size_weight": 0.5,
                "conflict_penalty_weight": 0.5,
                "health_weight": 0.5
            }
        )

        adjusted_score = base_score

        # dataset size effect
        adjusted_score *= (1 - sensitivity["dataset_size_weight"] + sensitivity["dataset_size_weight"] * size_factor)

        # conflict effect
        adjusted_score *= (1 - sensitivity["conflict_penalty_weight"] + sensitivity["conflict_penalty_weight"] * conflict_factor)

        # health effect
        adjusted_score *= (1 - sensitivity["health_weight"] + sensitivity["health_weight"] * health_factor)

        item["score"] = round(adjusted_score, 3)

        adjusted.append(item)

    return adjusted

def generate_justifications(ranked_insights, health, conflicts, df):
    justified = []

    health_score = health.get("health_score", 0)
    sample_size = len(df)

    for item in ranked_insights:
        score = item.get("score", 0)
        ctype = item.get("type", "unknown")

        boosts = []
        penalties = []

        # --- base reasoning ---
        base_signal = f"{ctype} signal strength {score}"

        # --- boosts ---
        if score > 0.7:
            boosts.append("strong statistical signal")

        if health_score > 80:
            boosts.append("high dataset quality")

        # --- penalties ---
        if health_score < 60:
            penalties.append("low dataset quality")

        if sample_size < 10:
            penalties.append("small dataset size")

        if conflicts:
            penalties.append("conflicting signals detected")

        # --- final explanation ---
        if len(penalties) == 0:
            final_reason = "Strong and reliable signal"
        elif len(penalties) == 1:
            final_reason = "Moderate reliability with minor constraints"
        else:
            final_reason = "Weak reliability due to multiple constraints"

        item["justification"] = {
            "base_signal": base_signal,
            "boosts": boosts,
            "penalties": penalties,
            "final_reason": final_reason
        }

        justified.append(item)

    return justified

def align_contradictions(
    narrative_summary,
    ranked_insights,
    final_insights,
    correlations
):
    """
    Ensures narrative language does not exaggerate
    the actual statistical evidence.
    """

    correlation_pairs = correlations.get("pairs", [])

    if not correlation_pairs:
        return narrative_summary, final_insights

    hierarchy = [
        "negligible",
        "weak",
        "moderate",
        "strong",
        "very strong"
    ]

    strongest_detected = "negligible"

    for pair in correlation_pairs:

        strength = pair.get("strength", "negligible")

        if hierarchy.index(strength) > hierarchy.index(strongest_detected):
            strongest_detected = strength

    adjusted_narrative = narrative_summary

    # Prevent exaggerated wording
    if strongest_detected in ["negligible", "weak"]:

        adjusted_narrative = re.sub(r'\bvery strong\b', 'weak', adjusted_narrative)
        adjusted_narrative = re.sub(r'\bstrong\b', 'weak', adjusted_narrative)
        adjusted_narrative = re.sub(r'\bmoderate\b', 'weak', adjusted_narrative)

    elif strongest_detected == "moderate":

        adjusted_narrative = re.sub(r'\bvery strong\b', 'moderate', adjusted_narrative)
        adjusted_narrative = re.sub(r'\bstrong\b', 'moderate', adjusted_narrative)

    elif strongest_detected == "strong":

        adjusted_narrative = re.sub(r'\bvery strong\b', 'strong', adjusted_narrative)

    # Controlled final summary generation
    if "summary" in final_insights:

        if strongest_detected == "negligible":

            final_insights["summary"] = (
                "The dataset shows negligible statistical relationships "
                "with limited analytical significance."
            )

        elif strongest_detected == "weak":

            final_insights["summary"] = (
                "The dataset shows weak statistical relationships "
                "with limited predictive strength."
            )

        elif strongest_detected == "moderate":

            final_insights["summary"] = (
                "The dataset shows moderate statistical relationships "
                "with mixed analytical strength."
            )

        elif strongest_detected == "strong":

            final_insights["summary"] = (
                "The dataset shows strong statistical relationships "
                "with reliable analytical patterns."
            )

        else:

            final_insights["summary"] = (
                "The dataset shows very strong statistical relationships "
                "with highly consistent patterns."
            )

    return adjusted_narrative, final_insights

def safe_list(x):
    return list(x) if x else []

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

def generate_contextual_synthesis(insights, correlations, anomalies):
    """
    Converts isolated analytical outputs into grouped business themes.
    """

    # ----------------------------
    # 1. Build variable interaction map
    # ----------------------------
    variable_map = defaultdict(list)

    corr_list = correlations.get("pairs", [])

    for c in corr_list:

        # handle dict format
        if isinstance(c, dict):
            pair = c.get("pair", "")
            strength = c.get("strength", "")
            pearson = c.get("pearson", 0)

        # handle string format
        elif isinstance(c, str):
            pair = c
            strength = ""
            pearson = 0

        else:
            continue

        
        if " vs " in pair:
          v1, v2 = pair.split(" vs ")
        else:
            continue

        v1 = v1.strip()
        v2 = v2.strip()

        # populate variable_map (THIS WAS COMPLETELY MISSING)
        variable_map[v1].append({
            "related_to": v2,
            "type": "correlation",
            "strength": strength,
            "value": pearson
        })

        variable_map[v2].append({
            "related_to": v1,
            "type": "correlation",
            "strength": strength,
            "value": pearson
        })

    # ----------------------------
    # 2. Build thematic clusters (rule-based grouping)
    # ----------------------------
    themes = []
    used = set()

    for var, relations in variable_map.items():
        if var in used:
            continue

        cluster = {
            "theme": None,
            "variables": set([var]),
            "signals": [],
            "confidence_components": []
        }

        for r in relations:
            cluster["variables"].add(r["related_to"])
            cluster["signals"].append(r)

            value = r.get("value", 0)
            if isinstance(value, (int, float)):
                cluster["confidence_components"].append(float(value))

        # mark ALL variables only after cluster is built
        for v in cluster["variables"]:
            used.add(v)

        variables_list = list(cluster["variables"])

        # ----------------------------
        # 3. Theme naming logic (rule-based abstraction)
        # ----------------------------
        if any("Salary" in v or "Compensation" in v for v in variables_list):
            theme_name = "Compensation and progression structure"
        elif any("Experience" in v or "Tenure" in v for v in variables_list):
            theme_name = "Experience-driven behavioral pattern"
        elif any("Score" in v or "Performance" in v for v in variables_list):
            theme_name = "Performance-linked variation pattern"
        else:
            theme_name = f"Cross-variable relationship: {', '.join(variables_list[:2])}"

        # ----------------------------
        # 4. Confidence scoring
        # ----------------------------
        

        if cluster["confidence_components"]:
            # Weighted: 70% max signal, 30% average — preserves strong relationships
            max_signal = max(cluster["confidence_components"])
            avg_signal = sum(cluster["confidence_components"]) / len(cluster["confidence_components"])
            confidence = 0.7 * max_signal + 0.3 * avg_signal
        else:
            confidence = 0.3   # neutral default, not 0.5

        # ----------------------------
        # 5. Assemble theme object
        # ----------------------------
        themes.append({
            "theme": theme_name,
            "variables": list(cluster["variables"]),
            "supporting_signals": cluster["signals"],
            "confidence": round(confidence, 3),
            "reasoning_path": [
                "variables clustered by correlation adjacency",
                "signals aggregated from shared relationships",
                "confidence derived from correlation strength aggregation"
            ]
        })

    # ----------------------------
    # 6. Cross-variable patterns
    # ----------------------------
    cross_variable_patterns = []

    for t in themes:
        if len(t["variables"]) >= 3:
            cross_variable_patterns.append({
                "pattern": "multi-factor interaction",
                "theme": t["theme"],
                "variables": t["variables"],
                "interpretation": "multiple variables move in coordinated statistical structure"
            })

    # ----------------------------
    # 7. Emergent behaviors (simple heuristic layer)
    # ----------------------------
    emergent_behaviors = []

    strong_themes = [t for t in themes if t["confidence"] > 0.7]

    if len(strong_themes) >= 2:
        emergent_behaviors.append({
            "behavior": "structured system dynamics",
            "explanation": "multiple strong relational clusters indicate systemic rather than isolated behavior",
            "themes": [t["theme"] for t in strong_themes]
        })

    # ----------------------------
    # 8. Conflict-aware synthesis
    # ----------------------------
    conflicting_interpretations = []

    for a in anomalies:
        conflicting_interpretations.append({
            "variable": a.get("variable", ""),
            "note": "anomaly may distort local correlation reliability",
            "impact": "reduces confidence in nearby relational clusters"
        })

    # ----------------------------
    # Final output
    # ----------------------------
    return {
        "themes": themes,
        "cross_variable_patterns": cross_variable_patterns,
        "emergent_behaviors": emergent_behaviors,
        "conflicting_interpretations": conflicting_interpretations
    }

def generate_cross_theme_reasoning(contextual_synthesis, ranked_insights, conflicts):
    """
    Step 10: Cross-theme reasoning + executive synthesis layer
    """

    themes = contextual_synthesis.get("themes", [])

    if not themes:
        return {
            "executive_themes": [],
            "system_interpretation": "",
            "confidence": 0
        }

    # ----------------------------
    # 1. Identify dominant themes
    # ----------------------------
    sorted_themes = sorted(
        themes,
        key=lambda t: t.get("confidence", 0),
        reverse=True
    )

    dominant_themes = sorted_themes[:3]

    # ----------------------------
    # 2. Detect theme interactions
    # ----------------------------
    interactions = []

    for i in range(len(sorted_themes)):
        for j in range(i + 1, len(sorted_themes)):

            t1 = sorted_themes[i]
            t2 = sorted_themes[j]

            v1 = set(t1.get("variables", []))
            v2 = set(t2.get("variables", []))

            overlap = len(v1.intersection(v2))

            if overlap > 0:
                interaction_type = "reinforcing"
            else:
                interaction_type = "independent"

            interactions.append({
                "theme_a": t1["theme"],
                "theme_b": t2["theme"],
                "interaction": interaction_type,
                "overlap_score": overlap
            })

    # ----------------------------
    # 3. Build system-level interpretation
    # ----------------------------
    system_signals = []

    for t in dominant_themes:
        system_signals.append(
            f"{t['theme']} appears structurally significant"
        )

    if len(dominant_themes) >= 2:
        system_interpretation = (
            "The dataset exhibits multiple interacting structural patterns. "
            + " ".join(system_signals)
        )
    else:
        system_interpretation = (
            "The dataset is primarily driven by a single dominant structural pattern. "
            + " ".join(system_signals)
        )

    # ----------------------------
    # 4. Conflict pressure integration
    # ----------------------------
    conflict_pressure = len(conflicts) / (len(ranked_insights) + 1)

    if conflict_pressure > 0.3:
        system_interpretation += (
            " However, significant conflicting signals reduce overall interpretability."
        )

    # ----------------------------
    # 5. Final executive confidence
    # ----------------------------
    avg_conf = sum(t.get("confidence", 0) for t in dominant_themes) / len(dominant_themes)

    final_confidence = max(0, min(1, avg_conf - conflict_pressure * 0.2))

    # ----------------------------
    # Output
    # ----------------------------
    return {
        "dominant_themes": dominant_themes,
        "theme_interactions": interactions,
        "system_interpretation": system_interpretation,
        "confidence": round(final_confidence, 3)
    }

def generate_executive_synthesis(
    contextual_synthesis,
    cross_theme_reasoning,
    ranked_insights,
    conflicts,
    analytical_stability
):
    """
    Step 11: Executive Decision Synthesis Layer
    Converts analytical reasoning into decision-oriented output.
    """

    themes = contextual_synthesis.get("themes", [])
    dominant_themes = cross_theme_reasoning.get("dominant_themes", [])

    stability_score = analytical_stability.get("score") or analytical_stability.get("confidence") or 50
    stability_label = analytical_stability.get("label", "unknown")

    # ----------------------------
    # 1. Extract key drivers
    # ----------------------------
    key_drivers = [
        t.get("theme")
        for t in dominant_themes[:3]
        if t.get("theme")
    ]

    # ----------------------------
    # 2. Identify risk signals
    # ----------------------------
    risk_signals = []

    if stability_score < 60:
        risk_signals.append("Low analytical stability indicates reduced confidence in structural patterns")

    if len(conflicts) > 2:
        risk_signals.append("Multiple conflicting signals detected across dataset relationships")

    weak_themes = [t for t in themes if t.get("confidence", 0) < 0.4]
    if len(weak_themes) > len(themes) / 2:
        risk_signals.append("Majority of extracted patterns show weak structural confidence")

    # ----------------------------
    # 3. Identify opportunity signals
    # ----------------------------
    opportunity_signals = []

    strong_themes = [t for t in themes if t.get("confidence", 0) > 0.7]

    for t in strong_themes[:3]:
        opportunity_signals.append(
            f"Strong structural relationship observed in {t.get('theme')}"
        )

    # ----------------------------
    # 4. Decision framing (non-prescriptive)
    # ----------------------------
    if stability_score > 75 and strong_themes:
        decision_frame = "Dataset shows reliable structural patterns suitable for strategic interpretation"
    elif stability_score > 50:
        decision_frame = "Dataset shows moderate reliability; insights should be used with contextual caution"
    else:
        decision_frame = "Dataset shows unstable patterns; interpretations should be treated as exploratory"

    # ----------------------------
    # 5. Executive summary compression
    # ----------------------------
    summary_parts = []

    if key_drivers:
        summary_parts.append(
            "Primary structural drivers: " + ", ".join(key_drivers)
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

    # ----------------------------
    # 6. Final confidence adjustment
    # ----------------------------
    
    top_themes = dominant_themes[:3]

    if not top_themes:
        base_confidence = 0.5
    else:
        base_confidence = sum(t.get("confidence", 0) for t in top_themes) / len(top_themes)
        
    stability_norm = stability_score / 100

    final_confidence = (0.7 * base_confidence) + (0.3 * stability_norm)

    final_confidence = max(0.1, min(final_confidence, 0.99))

    # ----------------------------
    # Output
    # ----------------------------
    return {
        "executive_summary": executive_summary,
        "decision_frame": decision_frame,
        "key_drivers": key_drivers,
        "risk_signals": risk_signals,
        "opportunity_signals": opportunity_signals,
        "confidence": round(max(final_confidence, 0.1), 3),  # floor
        "score": round(max(final_confidence, 0.1) * 100, 2), # ← ADD THIS
        "stability_label": stability_label
    }

def generate_recommendations(
    executive_synthesis,
    cross_theme_reasoning,
    contextual_synthesis,
    ranked_insights
):
   
    recommendations = []

    themes = contextual_synthesis.get("themes", [])

    # Robust extraction with fallback chain
    stability = (
        executive_synthesis.get("confidence")
        or cross_theme_reasoning.get("confidence")
        or 0.3   # never let it be 0
    )

    # ----------------------------
    # 1. Compensation-related logic
    # ----------------------------
    for t in themes:
        if "compensation" in t.get("theme", "").lower():

            score = compute_unified_score(
                confidence=t.get("confidence", 0),
                stability=stability
            )

            recommendations.append({
                "action": "Review compensation alignment with performance and experience metrics",
                "reason": "Strong structural relationship detected between compensation and key drivers",
                "priority": map_priority_from_score(score),
                "confidence": round(score, 3)
            })

    # ----------------------------
    # 2. Experience dependency logic
    # ----------------------------
    for t in themes:
        if "experience" in t.get("theme", "").lower():

            score = compute_unified_score(
                confidence=t.get("confidence", 0),
                stability=stability
            )

            recommendations.append({
                "action": "Optimize hiring and promotion policies based on experience impact",
                "reason": "Experience shows measurable influence on system outcomes",
                "priority": map_priority_from_score(score),
                "confidence": round(score, 3)
            })

    # ----------------------------
    # 3. Performance mismatch logic
    # ----------------------------
    for t in themes:
        if "performance" in t.get("theme", "").lower():

            score = compute_unified_score(
                confidence=t.get("confidence", 0),
                stability=stability
            )

            recommendations.append({
                "action": "Re-evaluate performance scoring linkage with compensation models",
                "reason": "Performance signals show weaker or inconsistent correlation patterns",
                "priority": map_priority_from_score(score),
                "confidence": round(score, 3)
            })

    # ----------------------------
    # 4. System-level recommendation
    # ----------------------------

    if stability < 0.5:

        score = compute_unified_score(
            confidence=stability,
            stability=stability
        )

        recommendations.append({
            "action": "Avoid high-stakes decisions without further data validation",
            "reason": "Low system stability reduces reliability of derived insights",
            "priority": map_priority_from_score(score),
            "confidence": round(score, 3)
        })

    # ----------------------------
    # 5. Deduplicate (simple)
    # ----------------------------
    seen = set()
    unique = []

    for r in recommendations:
        if r["action"] not in seen:
            unique.append(r)
            seen.add(r["action"])

    # ----------------------------
    # Output
    # ----------------------------
    
    # Temporary

    print("STABILITY INPUT:", executive_synthesis)
    print("STABILITY VALUE:", executive_synthesis.get("score"), executive_synthesis.get("confidence"))
    
    return {
        "recommendations": unique,
        "total_recommendations": len(unique),
        "system_confidence": round(stability, 3)  # ← rounded, never 0
    }

def map_priority_from_score(score):
    if score >= 0.75:
        return "high"
    elif score >= 0.45:
        return "medium"
    else:
        return "low"
    
def map_priority(confidence, stability, is_key_theme=False):

    score = confidence * 0.7 + stability * 0.3

    if is_key_theme:
        score += 0.1
    if score >= 0.7:
        return "high"
    elif score >= 0.4:
        return "medium"
    else:
        return "low"

def create_initial_state(df=None, file_path=None, insights_input=None):
    """
    Build canonical pipeline state with safe defaults.
    All major functions read and write this dict.
    """
    state = {
        # core
        "df": df,
        "file_path": file_path,
        "rows": len(df) if df is not None else 0,
        "columns": len(df.columns) if df is not None else 0,

        # inputs
        "insights_input": insights_input or {"summary": [], "metrics": []},

        # intermediate / outputs (deterministic keys)
        "profile": {},
        "chart_path": None,
        "correlations": {"pairs": []},
        "dataset_health": {"health_score": 0, "completeness_score": 0.0, "anomaly_count": 0},
        "anomaly_details": [],
        "conflicts": [],
        "ranked_insights": [],
        "semantic_insights": [],
        "analytical_stability": {"score": 0, "confidence": 0.0, "label": "unknown", "summary": ""},

        "narrative_summary": "",
        "final_insights": {"key_findings": [], "supporting_evidence": [], "warnings": [], "summary": ""},

        "contextual_synthesis": {},
        "cross_theme_reasoning": {},
        "executive_synthesis": {},
        "recommendations": {}
    }

    return state

def generate_chart(state, column):
    state = state or {}
    df = state.get("df")
    file_path = state.get("file_path")
    state["chart_path"] = None

    if df is None or column not in df.columns:
        return state

    try:
        file_name = os.path.basename(file_path or "data.csv").replace(".csv", f"_{column}_chart.png")
        chart_fs_path = os.path.join("uploads", file_name)
        os.makedirs("uploads", exist_ok=True)

        plt.figure()
        df[column].dropna().hist()
        plt.title(f"{column} Distribution")
        plt.savefig(chart_fs_path)
        plt.close()

        state["chart_path"] = f"/charts/{file_name}"
    except Exception as e:
        # fail-safe: keep state, log minimally
        print("generate_chart error:", e)
        state["chart_path"] = None

    return state

def generate_profile(state):
    """
    Fill state['profile'] with per-column profiles.
    """
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
            # leave out empty columns (consistent with previous behavior)
            continue

        try:
            if pd.api.types.is_numeric_dtype(series):
                profile[col] = {
                    "type": "numeric",
                    "mean": round(float(clean.mean()), 2),
                    "median": round(float(clean.median()), 2),
                    "std": round(float(clean.std()), 2),
                    "min": float(clean.min()),
                    "max": float(clean.max())
                }
            else:
                top_value = None
                try:
                    top_value = str(clean.value_counts().idxmax())
                except Exception:
                    top_value = None

                profile[col] = {
                    "type": "categorical",
                    "unique_values": int(clean.nunique()),
                    "top_value": top_value
                }
        except Exception as e:
            # defensive: skip problematic columns
            print(f"generate_profile skipped column {col} due to", e)
            continue

    state["profile"] = profile
    return state

def compute_final_confidence(
    base,
    strength,
    health_score,
    sample_size,
    conflicts,
    anomalies
):
    """
    Computes calibrated confidence score in 0.1 .. 0.95 range.

    Philosophy:
    - strong statistical signals should survive moderate penalties
    - small datasets reduce certainty but should not destroy high-quality findings
    - poor dataset health reduces confidence meaningfully
    - conflicts/anomalies apply soft penalties, not catastrophic collapse
    """

    try:
        score = float(base)
    except Exception:
        score = 0.5

    # ----------------------------
    # Strength bonus
    # ----------------------------

    strength_bonus = {
        "negligible": 0.85,
        "weak": 0.92,
        "moderate": 1.0,
        "strong": 1.08,
        "very strong": 1.15
    }

    score *= strength_bonus.get(strength, 1.0)

    # ----------------------------
    # Sample size adjustment
    # ----------------------------

    # smoother scaling
    # avoids crushing small but valid datasets

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

    # ----------------------------
    # Dataset health adjustment
    # ----------------------------

    try:
        normalized_health = max(0.0, min(1.0, health_score / 100))
    except Exception:
        normalized_health = 0.5

    # softer health weighting
    health_factor = 0.75 + (normalized_health * 0.25)

    score *= health_factor

    # ----------------------------
    # Conflict penalty
    # ----------------------------

    conflict_count = conflicts if conflicts is not None else 0

    # soft diminishing penalties
    conflict_penalty = min(0.20, conflict_count * 0.05)

    score *= (1 - conflict_penalty)

    # ----------------------------
    # Anomaly penalty
    # ----------------------------

    anomaly_count = anomalies if anomalies is not None else 0

    anomaly_penalty = min(0.15, anomaly_count * 0.03)

    score *= (1 - anomaly_penalty)

    # ----------------------------
    # Clamp final score
    # ----------------------------

    return round(max(0.1, min(score, 0.95)), 3)

def run_analysis_pipeline(df, file_path, insights):

    health = generate_dataset_health(df)

    correlations = generate_correlation_analysis(df)

    conflicts = generate_conflict_detection(
        correlations,
        health,
        df
    )

    anomaly_details = generate_anomaly_explanations(df)

    raw_ranked_insights = generate_ranked_insights(
        df,
        correlations,
        health,
        insights
    )

    ranked_insights = calibrate_confidence(
        raw_ranked_insights,
        health,
        conflicts,
        anomaly_details,
        df
    )

    ranked_insights = deduplicate_insights(ranked_insights)

    ranked_insights = resolve_conflicts(
        conflicts,
        ranked_insights
    )

    ranked_insights = rebalance_scores(
        ranked_insights,
        health,
        conflicts,
        df
    )

    ranked_insights = generate_justifications(
        ranked_insights,
        health,
        conflicts,
        df
    )
    
    analytical_stability = generate_analytical_stability(
        health,
        ranked_insights,
        conflicts,
        anomaly_details,
        df
    )

    # Narrative layer
    narrative_summary = generate_narrative_summary(
        df,
        correlations,
        health
    )

    # Final insights layer
    final_insights = generate_final_insights(
        ranked_insights,
        conflicts,
        narrative_summary
    )

    # Alignment layer
    narrative_summary, final_insights = align_contradictions(
        narrative_summary,
        ranked_insights,
        final_insights,
        correlations
    )

    contextual_synthesis = generate_contextual_synthesis(
        insights=ranked_insights,
        correlations=correlations,
        anomalies=anomaly_details
    )

    cross_theme_reasoning = generate_cross_theme_reasoning(
        contextual_synthesis=contextual_synthesis,
        ranked_insights=ranked_insights,
        conflicts=conflicts
    )
    
    executive_synthesis = generate_executive_synthesis(
        contextual_synthesis=contextual_synthesis,
        cross_theme_reasoning=cross_theme_reasoning,
        ranked_insights=ranked_insights,
        conflicts=conflicts,
        analytical_stability=analytical_stability
    )
    
    recommendations = generate_recommendations(
        executive_synthesis = executive_synthesis,
        cross_theme_reasoning=cross_theme_reasoning,
        contextual_synthesis=contextual_synthesis,
        ranked_insights=ranked_insights
    )

    analytical_stability["confidence"] = analytical_stability["score"] / 100

    return {
        "rows": len(df),
        "columns": len(df.columns),

        "insights": insights,
        "profile": generate_profile(df),

        "correlations": correlations,
        "anomaly_details": anomaly_details,

        "dataset_health": health,
        "conflicts": conflicts,
      
        "analytical_stability": analytical_stability,
      
        "ranked_insights": ranked_insights,
      
        "contextual_synthesis": contextual_synthesis,
      
        "cross_theme_reasoning": cross_theme_reasoning,
      
        "narrative_summary": narrative_summary,
      
        "executive_synthesis": executive_synthesis,

        "final_insights": final_insights,

        "recommendations": recommendations
    }

def is_identifier_column(col_name, series):
    """
    Detect likely identifier columns that should not participate
    in statistical analysis.
    """

    if not col_name:
        return False

    name = col_name.lower().replace("_", "").replace(" ", "")

    identifier_keywords = [
        "id",
        "uuid",
        "employeeid",
        "userid",
        "customerid",
        "serial",
        "serialno",
        "index"
    ]

    # keyword match
    if any(keyword in name for keyword in identifier_keywords):
        return True

    # non-numeric columns cannot be identifier sequences here
    if not pd.api.types.is_numeric_dtype(series):
        return False

    clean = series.dropna()

    if len(clean) < 3:
        return False

    # high uniqueness ratio
    uniqueness_ratio = clean.nunique() / len(clean)

    if uniqueness_ratio > 0.95:

        # monotonic increasing/decreasing
        if clean.is_monotonic_increasing or clean.is_monotonic_decreasing:
            return True

        # integer-like sequential behavior
        diffs = clean.diff().dropna()

        if not diffs.empty and diffs.nunique() <= 2:
            return True

    return False

def generate_correlation_analysis(state):
    """
    Writes state['correlations'] = {"pairs": [...]}
    Each pair is a dict with keys: pair, pearson, strength, p_value, significance
    """
    state = state or {}
    df = state.get("df")

    results = []
    if df is None:
        state["correlations"] = {"pairs": results}
        return state

    numeric_df = df.select_dtypes(include=[np.number]).copy()

    # Remove likely identifier columns
    filtered_columns = []

    for col in numeric_df.columns:

        if not is_identifier_column(col, numeric_df[col]):
            filtered_columns.append(col)

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
            # pearsonr requires finite arrays
            col1_data = numeric_df[col1].dropna()
            col2_data = numeric_df[col2].dropna()
            # align indices
            align_idx = col1_data.index.intersection(col2_data.index)
            if len(align_idx) < 3:
                p_value = 1.0
            else:
                _, p_value = pearsonr(col1_data.loc[align_idx], col2_data.loc[align_idx])
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
            "significance": significance
        })

    state["correlations"] = {"pairs": results}
    return state

def generate_dataset_health(state):
    """
    Fills state['dataset_health'] with:
      - completeness_score (0..1)
      - anomaly_count (int)
      - health_score (0..100)
    """
    state = state or {}
    df = state.get("df")

    if df is None:
        state["dataset_health"] = {"completeness_score": 0.0, "anomaly_count": 0, "dominance_issues": 0, "health_score": 0.0}
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
        mean = series.mean()
        if mean != 0 and abs(std / mean) > 2:
            anomaly_count += 1

    health_score = round(max(0.0, min(100.0, completeness * 100 - anomaly_count * 5)), 2)

    state["dataset_health"] = {
        "completeness_score": round(completeness, 3),
        "anomaly_count": anomaly_count,
        "dominance_issues": 0,
        "health_score": health_score
    }

    return state

def generate_anomaly_explanations(state):
    """
    Populates state['anomaly_details'] with list of anomaly dicts.
    """
    state = state or {}
    df = state.get("df")
    anomalies = []

    if df is None:
        state["anomaly_details"] = anomalies
        return state

    numeric_df = df.select_dtypes(include=[np.number])

    for col in numeric_df.columns:
        series = numeric_df[col].dropna()
        if len(series) < 3:
            continue
        mean = series.mean()
        std = series.std()
        if std <= 0:
            continue
        for idx, val in series.items():
            try:
                if abs(val - mean) > 3 * std:
                    anomalies.append({
                        "column": col,
                        "row_index": int(idx),
                        "value": float(val),
                        "type": "outlier",
                        "severity": "high"
                    })
            except Exception:
                continue

    state["anomaly_details"] = anomalies
    return state

def compute_unified_score(confidence, stability, significance=None, anomaly_penalty=0):
    """
    Balanced scoring model:
    confidence = signal strength
    stability = reliability modifier (not dominant factor)
    """

    # signal core (dominant)
    score = 0.7 * confidence + 0.2 * stability

    # significance boost
    if significance:
        if isinstance(significance, str):
            if "high" in significance.lower():
                score += 0.1
            elif "not" in significance.lower():
                score -= 0.05

    # anomaly penalty
    score -= anomaly_penalty * 0.15

    # clamp
    score = max(0, min(1, score))

    # floor (prevents dead system)
    score = max(score, 0.15)

    return score
    
def generate_ranked_insights(state):
    """
    Produces an initial ranked_insights list and stores in state['ranked_insights'].
    Each item: {type, priority, message, score, strength, ...}
    """
    state = state or {}
    correlations = state.get("correlations", {}) or {}
    pairs = correlations.get("pairs", []) or []
    ranked = []

    for item in pairs:
        strength_value = abs(item.get("pearson", 0))
        semantic_strength = item.get("strength", "weak")
        significance = item.get("significance", "not significant")

        if strength_value > 0.7:
            priority = "high"
        elif strength_value > 0.4:
            priority = "medium"
        else:
            priority = "low"

        pair_name = item.get("pair", "unknown pair")
        pearson_value = item.get("pearson", 0)

        direction = "positive" if pearson_value >= 0 else "negative"

        if semantic_strength in ["strong", "very strong"]:
            explanation = (
                f"{pair_name} demonstrates a {semantic_strength} {direction} statistical relationship"
            )
        elif semantic_strength == "moderate":
            explanation = (
                f"{pair_name} shows a moderate {direction} statistical relationship"
            )
        else:
            explanation = (
                f"{pair_name} exhibits weak statistical alignment with limited analytical significance"
            )

        if significance == "not significant":
            explanation += ", though the statistical evidence is currently limited"
        elif significance == "highly significant":
            explanation += " with highly reliable statistical evidence"

        ranked.append({
            "type": "correlation",
            "priority": priority,
            "message": explanation,
            "score": round(strength_value, 3),
            "strength": semantic_strength,
            # preserve the base pearson & significance for later reasoning
            "pearson": pearson_value,
            "significance": significance
        })

    ranked.sort(key=lambda x: x.get("score", 0), reverse=True)
    state["ranked_insights"] = ranked[:10]
    return state

def calibrate_confidence(state):
    """
    Read state['ranked_insights'], apply compute_final_confidence, update items,
    set item['priority'], and write back to state['ranked_insights'].
    """
    if not state or not isinstance(state, dict):
        return state

    insights = state.get("ranked_insights", []) or []
    health_score = (state.get("dataset_health") or {}).get("health_score", 0)
    sample_size = state.get("rows", 0)
    conflict_count = len(state.get("conflicts") or [])
    anomaly_count = (state.get("dataset_health") or {}).get("anomaly_count") or len(state.get("anomaly_details") or [])

    base_map = {"very_high": 1.0, "high": 0.75, "medium": 0.5, "low": 0.25}

    calibrated = []
    for item in insights:
        conf = item.get("confidence", 0.5)
        if isinstance(conf, str):
            base = base_map.get(conf, 0.5)
        else:
            try:
                base = float(conf)
            except Exception:
                base = 0.5

        strength = item.get("strength", "weak")

        final_conf = compute_final_confidence(
            base=base,
            strength=strength,
            health_score=health_score,
            sample_size=sample_size,
            conflicts=conflict_count,
            anomalies=anomaly_count
        )

        item["confidence"] = round(final_conf, 3)
        item["priority"] = map_priority_from_score(final_conf)
        calibrated.append(item)

    state["ranked_insights"] = calibrated
    return state

def deduplicate_insights(state):
    """
    Deduplicates on message text. Keeps first occurrence.
    """
    state = state or {}
    ranked_insights = state.get("ranked_insights") or []
    seen = set()
    cleaned = []
    for item in ranked_insights:
        key = (item.get("message") or "").lower().strip()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(item)
    state["ranked_insights"] = cleaned
    return state

def resolve_conflicts(state):
    """
    Analyze the canonical pipeline `state` and populate state['conflicts'] with detected issues.
    Returns the updated state dict.
    Each conflict is a dict with keys: type, severity ('low'|'medium'|'high'), message, and optional details.
    """
    # Defensive defaults
    if state is None or not isinstance(state, dict):
        return {"conflicts": []}

    conflicts = []
    df = state.get("df")
    # rows fallback to an explicit state entry or len(df)
    rows = state.get("rows")
    if rows is None:
        try:
            rows = len(df) if df is not None else 0
        except Exception:
            rows = 0

    correlations = safe_list((state.get("correlations") or {}).get("pairs"))
    dataset_health = state.get("dataset_health") or {}
    health_score = dataset_health.get("health_score", dataset_health.get("health", 0))
    try:
        health_score = float(health_score)
    except Exception:
        health_score = 0.0

    anomaly_details = state.get("anomaly_details") or []
    anomaly_count = dataset_health.get("anomaly_count", len(anomaly_details) if anomaly_details else 0)
    try:
        anomaly_count = int(anomaly_count)
    except Exception:
        anomaly_count = len(anomaly_details) if anomaly_details else 0

    # 1) Strong correlations vs dataset health
    strong_relationships = [p for p in correlations if p.get("strength") in ("strong", "very strong")]
    if strong_relationships:
        if health_score < 60:
            conflicts.append({
                "type": "correlation_vs_health",
                "severity": "high",
                "message": "Strong correlations exist but dataset health is low; results may be unreliable.",
                "affected_pairs": [p.get("pair") for p in strong_relationships[:10]],
                "health_score": health_score
            })
        elif health_score < 80:
            conflicts.append({
                "type": "correlation_vs_health",
                "severity": "medium",
                "message": "Strong correlations detected but dataset health is not optimal.",
                "affected_pairs": [p.get("pair") for p in strong_relationships[:10]],
                "health_score": health_score
            })

    # 2) Small sample size warning (may inflate correlations)
    if rows and rows < 10 and correlations:
        conflicts.append({
            "type": "sample_size_warning",
            "severity": "medium",
            "message": f"Small dataset (n={rows}) may produce unstable or inflated correlation estimates.",
            "sample_size": rows
        })

    # 3) High-quality dataset but few/absent strong signals
    if health_score > 80 and not strong_relationships:
        conflicts.append({
            "type": "signal_absence",
            "severity": "low",
            "message": "Dataset quality is high but there are few strong statistical relationships.",
            "health_score": health_score
        })

    # 4) Strong correlations that are not statistically significant
    for p in strong_relationships:
        p_value = p.get("p_value", 1.0)
        try:
            pv = float(p_value)
        except Exception:
            pv = 1.0
        # treat p >= 0.05 as not significant for the purposes of conflict detection
        if pv >= 0.05:
            conflicts.append({
                "type": "strong_not_significant",
                "severity": "high",
                "message": f"Pair {p.get('pair')} shows a large effect ({p.get('pearson')}) but is not statistically significant (p={pv}).",
                "pair": p.get("pair"),
                "pearson": p.get("pearson"),
                "p_value": pv
            })

    # 5) Anomalies / outliers summary
    if anomaly_count > 0:
        ratio = (anomaly_count / rows) if rows and rows > 0 else 1.0
        if ratio >= 0.10:
            sev = "high"
        elif ratio >= 0.02:
            sev = "medium"
        else:
            sev = "low"
        conflicts.append({
            "type": "anomalies_detected",
            "severity": sev,
            "message": f"{anomaly_count} anomaly events detected (~{ratio:.2%} of rows).",
            "anomaly_count": anomaly_count,
            "anomaly_ratio": round(ratio, 4)
        })

    # 6) Dominance (single-value dominated columns)
    dominance = dataset_health.get("dominance_issues", 0)
    try:
        dom_count = int(dominance)
    except Exception:
        dom_count = 0
    if dom_count > 0:
        conflicts.append({
            "type": "dominance_issues",
            "severity": "medium",
            "message": f"{dom_count} column(s) appear to be dominated by a single value, which can bias analysis.",
            "dominance_issues": dom_count
        })

    # 7) Duplicate correlation entries (data hygiene)
    pair_names = [p.get("pair") for p in correlations if p.get("pair")]
    dup_pairs = [x for x in set(pair_names) if pair_names.count(x) > 1]
    if dup_pairs:
        conflicts.append({
            "type": "duplicate_correlation_entries",
            "severity": "low",
            "message": f"Duplicate correlation entries detected for pairs: {', '.join(dup_pairs[:10])}.",
            "duplicates": dup_pairs[:20]
        })

    # 8) Columns with high missingness
    if df is not None:
        try:
            # missing_by_col are percentages (0..100)
            missing_by_col = (df.isna().mean() * 100).to_dict()
            cols_high_missing = [col for col, pct in missing_by_col.items() if pct >= 50.0]
            cols_medium_missing = [col for col, pct in missing_by_col.items() if 20.0 <= pct < 50.0]
            if cols_high_missing:
                conflicts.append({
                    "type": "high_missingness",
                    "severity": "high",
                    "message": f"Columns with >=50% missing values: {len(cols_high_missing)}",
                    "columns": cols_high_missing[:20],
                    "percent_missing": {c: round(missing_by_col.get(c, 0.0), 2) for c in cols_high_missing[:20]}
                })
            elif cols_medium_missing:
                conflicts.append({
                    "type": "moderate_missingness",
                    "severity": "medium",
                    "message": f"Columns with 20–50% missing values: {len(cols_medium_missing)}",
                    "columns": cols_medium_missing[:20]
                })
        except Exception as e:
            # don't fail the pipeline because a missingness check failed
            print("resolve_conflicts: missingness check failed:", e)

    # De-duplicate conflicts (simple heuristic by type+message)
    seen = set()
    unique_conflicts = []
    for c in conflicts:
        key = (c.get("type"), c.get("message"))
        if key not in seen:
            seen.add(key)
            unique_conflicts.append(c)

    # Write back into state and return
    state["conflicts"] = unique_conflicts
    return state

def detect_anomalies(state):
    """
    Robust anomaly detection using IQR method.

    Detects outliers using:
        lower = Q1 - 1.5 * IQR
        upper = Q3 + 1.5 * IQR

    Updates:
    - state["anomaly_details"]
    - state["dataset_health"]["anomaly_count"]
    """

    if not state or not isinstance(state, dict):
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

        # skip identifier-like columns
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

            outlier_mask = (
                (df[col] < lower_bound) |
                (df[col] > upper_bound)
            )

            outlier_count = int(outlier_mask.sum())

            if outlier_count > 0:

                details.append({
                    "column": col,
                    "count": outlier_count,
                    "pct": round(
                        outlier_count / max(1, len(series)),
                        4
                    ),
                    "lower_bound": round(float(lower_bound), 2),
                    "upper_bound": round(float(upper_bound), 2)
                })

                row_mask = row_mask | outlier_mask.fillna(False)

        except Exception as e:
            print(f"Anomaly detection error for {col}: {e}")

    total_row_anomalies = int(row_mask.sum())

    state["anomaly_details"] = details

    dh = state.setdefault("dataset_health", {})
    dh["anomaly_count"] = total_row_anomalies

    return state

def generate_final_insights(ranked_insights, conflicts, narrative_summary):
    key_findings = []
    supporting_evidence = []
    warnings = []

    for item in ranked_insights:
        if item["type"] == "correlation" and item["priority"] in ["high", "medium"]:
            key_findings.append(item["message"])

        if item["type"] == "variability":
            supporting_evidence.append(item["message"])

    for c in conflicts:
        warnings.append(c.get("message", ""))

    return {
        "key_findings": key_findings[:5],
        "supporting_evidence": supporting_evidence[:5],
        "warnings": warnings[:5],
        "summary": narrative_summary if narrative_summary else "No narrative generated"
    }

def analyze_data(file_path):
    df = pd.read_csv(file_path)
    state = create_initial_state(df=df, file_path=file_path)
    state["rows"] = len(df)
    state["columns"] = len(df.columns)

    # Profile and basic artifacts
    state = generate_profile(state)

    # Find meaningful chartable numeric column
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()

    filtered_cols = []

    for col in num_cols:

        if not is_identifier_column(col, df[col]):
            filtered_cols.append(col)

    chart_col = None

    # Prefer high-variance meaningful features
    if filtered_cols:

        variance_map = {}

        for col in filtered_cols:

            try:
                variance_map[col] = df[col].std()
            except Exception:
                variance_map[col] = 0

        sorted_cols = sorted(
            variance_map.items(),
            key=lambda x: x[1],
            reverse=True
        )

        chart_col = sorted_cols[0][0]

    elif num_cols:
        # fallback
        chart_col = num_cols[0]

    elif len(df.columns):
        chart_col = df.columns[0]

    if chart_col:
        state = generate_chart(state, chart_col)

    # Correlations, health, anomalies, conflicts
    state = generate_correlation_analysis(state)
    state = generate_dataset_health(state)
    state = detect_anomalies(state)
    state = resolve_conflicts(state)

    # Build a simple ranked_insights structure from correlations (example)
    corr_pairs = state.get("correlations", {}).get("pairs", [])
    ranked = []
    for p in sorted(corr_pairs, key=lambda x: -abs(x.get("pearson", 0)))[:20]:
        pearson_value = abs(p.get("pearson", 0))

        if pearson_value >= 0.9:
            base_confidence = 0.9

        elif pearson_value >= 0.75:
            base_confidence = 0.8

        elif pearson_value >= 0.6:
            base_confidence = 0.7

        elif pearson_value >= 0.4:
            base_confidence = 0.55

        else:
            base_confidence = 0.4

        ranked.append({
            "pair": p.get("pair"),
            "pearson": p.get("pearson"),
            "strength": p.get("strength"),
            "confidence": base_confidence
        })

    state["ranked_insights"] = ranked

    # Calibrate and stability
    state = calibrate_confidence(state)
    state = generate_analytical_stability(state)

    # Semantic & narrative
    state = add_semantic_insights_to_state(state)
    state["narrative_summary"] = generate_narrative_summary(state.get("df"), state.get("correlations", {}), state.get("dataset_health", {}))

    # Final assembly: ensure main.py keys exist (lightweight)
    state.setdefault("final_insights", {"key_findings": state.get("insights", [])})
    state.setdefault("contextual_synthesis", {})
    state.setdefault("cross_theme_reasoning", {})
    state.setdefault("executive_synthesis", {})
    state.setdefault("recommendations", {})

    return state