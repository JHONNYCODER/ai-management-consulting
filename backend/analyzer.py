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

def generate_chart(df, column, file_path):
    file_name = os.path.basename(file_path).replace(".csv", "_chart.png")
    chart_fs_path = os.path.join("uploads", file_name)
    os.makedirs("uploads", exist_ok=True)

    plt.figure()
    df[column].dropna().hist()
    plt.title(f"{column} Distribution")
    plt.savefig(chart_fs_path)
    plt.close()

    return f"/charts/{file_name}"

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

    numeric_cols = df.select_dtypes(include=["number"]).columns
    categorical_cols = df.select_dtypes(exclude=["number"]).columns

    summary_parts = []

    sample_size = len(df)

    correlation_pairs = correlations.get("pairs", [])
    
    health_score = (
        health.get("health_score")
        or health.get("completeness_score")
        or 0
    )
    
    # Dataset quality interpretation
    if health_score >= 80:
        summary_parts.append(
            "The dataset is high quality with minimal structural issues."
        )

    elif health_score >= 50:
        summary_parts.append(
            "The dataset is moderately reliable but contains some quality concerns."
        )

    else:
        summary_parts.append(
            "The dataset contains significant quality or consistency issues."
        )

    # Correlation interpretation
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

        direction = "positive"

        if corr_value < 0:
            direction = "negative"

        summary_parts.append(
            f"The dataset demonstrates a very strong {direction} relationship "
            f"between {pair_name}."
        )

        if len(strong_pairs) > 1:
            summary_parts.append(
                f"Multiple variables exhibit strong statistical alignment patterns."
            )

    elif moderate_pairs:

        top_pair = max(
            moderate_pairs,
            key=lambda x: abs(x.get("pearson", 0))
        )

        pair_name = top_pair["pair"]
        corr_value = top_pair["pearson"]

        direction = "positive"

        if corr_value < 0:
            direction = "negative"

        summary_parts.append(
            f"A moderate {direction} relationship exists between {pair_name}."
        )

    else:

        summary_parts.append(
            "Most detected statistical relationships are relatively weak."
        )

    # Reliability interpretation
    if sample_size < 10:

        summary_parts.append(
            "Observed patterns should be interpreted cautiously due to limited sample size."
        )

    elif sample_size > 100 and health_score > 80:

        summary_parts.append(
            "Observed analytical patterns appear stable across the dataset."
        )

    # Dataset structure
    summary_parts.append(
        f"The dataset contains {len(numeric_cols)} numeric and "
        f"{len(categorical_cols)} categorical features."
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

def calibrate_confidence(
    ranked_insights,
    health,
    conflicts,
    anomaly_details,
    df
):
    calibrated = []

    health_score = health.get("health_score", 0)
    sample_size = len(df)
    conflict_count = len(conflicts) if conflicts else 0
    anomaly_count = len(anomaly_details) if anomaly_details else 0

    for item in ranked_insights:

        confidence = item.get("confidence", 0.5)

        base_map = {
            "very_high": 1.0,
            "high": 0.75,
            "medium": 0.5,
            "low": 0.25
        }

        if isinstance(confidence, str):
            base = base_map.get(confidence, 0.5)
        else:
            base = float(confidence)

        strength = item.get("strength", "weak")

        item["confidence"] = compute_final_confidence(
            base=base,
            strength=strength,
            health_score=health_score,
            sample_size=sample_size,
            conflicts=conflict_count,
            anomalies=anomaly_count
        )

        calibrated.append(item)

def generate_analytical_stability(
    health,
    ranked_insights,
    conflicts,
    anomaly_details,
    df
):

    # ----------------------------
    # Base score (normalized safer)
    # ----------------------------

    base_score = health.get("health_score", 50)

    sample_size = len(df)
    
    # ensure bounded baseline
    score = max(0, min(100, float(base_score)))

    size_factor = min(1.0, sample_size / 1000)

    conflict_count = len(conflicts) if conflicts else 0
    anomaly_count = len(anomaly_details) if anomaly_details else 0

    # ----------------------------
    # Insight signal strength
    # ----------------------------
    significant_count = 0
    ranked_insights = ranked_insights or []
    total = len(ranked_insights)

    def normalize_confidence(c):
        if isinstance(c, str):
            return {
                "very_high": 0.9,
                "high": 0.8,
                "medium": 0.5,
                "low": 0.2
            }.get(c, 0.3)

        if isinstance(c, (int, float)):
            return max(0.0, min(float(c), 1.0))

        return 0.3


    for item in ranked_insights:
        confidence = normalize_confidence(item.get("confidence", 0.5))

        if confidence >= 0.5:
            significant_count += 1

    reliability_ratio = (significant_count / total) if total > 0 else 0

    stability_score = (
        0.5 * reliability_ratio +
        0.3 * (size_factor) +
        0.2 * (1 - min(1, (conflict_count + anomaly_count) / 10))
    ) * 100

    # ----------------------------
    # Final clamp
    # ----------------------------
    score = max(0, min(100, round(score)))

    # ----------------------------
    # Labeling (clean thresholds)
    # ----------------------------
    if score >= 75:
        label = "stable"
    elif score >= 50:
        label = "moderately stable"
    else:
        label = "unstable"

    # ----------------------------
    # Summary (slightly more informative)
    # ----------------------------
    if label == "stable":
        summary = "High consistency across signals with reliable structural patterns."

    elif label == "moderately stable":
        summary = "Moderate reliability with some uncertainty in signal strength."

    else:
        summary = "Low stability due to weak or inconsistent analytical signals."

    # ----------------------------
    # Output (single source of truth)
    # ----------------------------
    stability_score = max(0, min(100, round(stability_score)))

    if stability_score >= 75:
        label = "stable"
    elif stability_score >= 50:
        label = "moderately stable"
    else:
        label = "unstable"
    
    return {
        "score": stability_score,
        "confidence": round(stability_score / 100, 3),
        "label": label,
        "summary": summary
    }

def deduplicate_insights(ranked_insights):
    ranked_insights = ranked_insights or []
    
    seen = set()
    cleaned = []

    for item in ranked_insights:
        key = item["message"].lower().strip()

        # crude but effective dedupe
        if key in seen:
            continue

        seen.add(key)
        cleaned.append(item)

    return cleaned

def resolve_conflicts(conflicts, ranked_insights):
    if not conflicts:
        return ranked_insights

    for item in ranked_insights:
        for c in conflicts:
            if c["type"] == "sample_size_warning" and item["type"] == "correlation":
                item["confidence"] = "medium"
                item["priority"] = "medium"
            if c["type"] == "correlation_vs_health" and item["type"] == "correlation":
                if item.get("score", 0) > 0.8:
                    item["confidence"] = "medium"

    return ranked_insights

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

def classify_correlation_strength(value):
    """
    Converts correlation values into semantic strength categories.
    This becomes the canonical strength source across the pipeline.
    """

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

def map_priority(confidence, stability, is_key_theme=False):
    """
    Converts analytical signals into business priority.
    """

    score = confidence * 0.7 + stability * 0.3

    if is_key_theme:
        score += 0.1

    if score >= 0.7:
        return "high"
    elif score >= 0.4:
        return "medium"
    else:
        return "low"

def compute_final_confidence(
    base,
    strength,
    health_score,
    sample_size,
    conflicts,
    anomalies
):

    score = base

    size_factor = min(1.0, sample_size / 30)
    score *= (0.7 + 0.3 * size_factor)

    score *= (0.7 + 0.3 * (health_score / 100))

    score *= (1 - min(0.3, 0.1 * conflicts))

    score *= (1 - min(0.25, 0.08 * anomalies))

    if strength in ["strong", "very strong"]:
        score *= 1.1

    return max(0.1, min(score, 0.95))

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

def generate_profile(df):
    profile = {}

    for col in df.columns:
        series = df[col]

        if pd.api.types.is_numeric_dtype(series):
            clean = series.dropna()

            if clean.empty:
                continue

            profile[col] = {
                "type": "numeric",
                "mean": round(float(clean.mean()), 2),
                "median": round(float(clean.median()), 2),
                "std": round(float(clean.std()), 2),
                "min": float(clean.min()),
                "max": float(clean.max())
            }

        else:
            clean = series.dropna()

            if clean.empty:
                continue

            top_value = clean.value_counts().idxmax()

            profile[col] = {
                "type": "categorical",
                "unique_values": int(clean.nunique()),
                "top_value": str(top_value)
            }

    return profile

def generate_correlation_analysis(df):
    numeric_df = df.select_dtypes(include=[np.number])

    if numeric_df.shape[1] < 2:
        return {}

    pearson_corr = numeric_df.corr(method="pearson")

    results = []
    columns = numeric_df.columns

    for col1, col2 in itertools.combinations(columns, 2):
        val = pearson_corr.loc[col1, col2]

        if pd.isna(val):
            continue

        try:
            _, p_value = pearsonr(
                numeric_df[col1],
                numeric_df[col2]
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
            "significance": significance
        })

    return {
        "pairs": results
    }

def generate_dataset_health(df):
    import numpy as np

    total_cells = df.shape[0] * df.shape[1]
    missing_cells = df.isna().sum().sum()

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

    health_score = round(completeness * 100 - anomaly_count * 5, 2)

    return {
        "completeness_score": round(completeness, 3),
        "anomaly_count": anomaly_count,
        "dominance_issues": 0,
        "health_score": health_score
    }

def generate_anomaly_explanations(df):
    import numpy as np

    anomalies = []
    numeric_df = df.select_dtypes(include=[np.number])

    for col in numeric_df.columns:
        series = numeric_df[col].dropna()

        if len(series) < 3:
            continue

        mean = series.mean()
        std = series.std()

        for idx, val in series.items():
            if std > 0 and abs(val - mean) > 3 * std:
                anomalies.append({
                    "column": col,
                    "row_index": int(idx),
                    "value": float(val),
                    "type": "outlier",
                    "severity": "high"
                })

    return anomalies

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

def map_priority_from_score(score):
    if score >= 0.75:
        return "high"
    elif score >= 0.45:
        return "medium"
    else:
        return "low"
    
def generate_ranked_insights(df, correlations, health, insights):
    ranked = []

    # Correlation signals
    if correlations and "pairs" in correlations:

        for item in correlations["pairs"]:

            strength_value = abs(item.get("pearson", 0))
            semantic_strength = item.get("strength", "weak")
            significance = item.get("significance", "not significant")
            
            if strength_value > 0.7:
                priority = "high"
            elif strength_value > 0.4:
                priority = "medium"
            else:
                priority = "low"

        
            pair_name = item["pair"]
            pearson_value = item.get("pearson", 0)

            direction = "positive"

            if pearson_value < 0:
                direction = "negative"

            if semantic_strength in ["strong", "very strong"]:

                explanation = (
                    f"{pair_name} demonstrates a {semantic_strength} "
                    f"{direction} statistical relationship"
                )

            elif semantic_strength == "moderate":

                explanation = (
                    f"{pair_name} shows a moderate "
                    f"{direction} statistical relationship"
                )

            else:

                explanation = (
                    f"{pair_name} exhibits weak statistical alignment "
                    f"with limited analytical significance"
                )

            if significance == "not significant":

                explanation += (
                    ", though the statistical evidence is currently limited"
                )

            elif significance == "highly significant":

                explanation += (
                    " with highly reliable statistical evidence"
                )

            ranked.append({
                "type": "correlation",
                "priority": priority,
                "message": explanation,
                "score": round(strength_value, 3),
                "strength": semantic_strength
            })


    ranked.sort(key=lambda x: x["score"], reverse=True)

    return ranked[:10]

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

    insights = {
        "summary": [],
        "metrics": []
    }

    numeric_columns = df.select_dtypes(include=["number"]).columns.tolist()
    
    for col in numeric_columns:
        series = df[col].dropna()

        if series.empty:
            continue

        mean_val = series.mean()
        std_val = series.std()

        insights["metrics"].append({
            "column": col,
            "mean": round(float(mean_val), 2),
            "std": round(float(std_val), 2),
            "min": float(series.min()),
            "max": float(series.max())
        })

        if std_val > mean_val:
            insights["summary"].append(f"{col} shows high variability")
        else:
            insights["summary"].append(f"{col} is relatively stable")

    chart_path = None
    if numeric_columns:
        try:
            chart_path = generate_chart(df, numeric_columns[0], file_path)
        except Exception as e:
            print("Chart error:", e)
    
    # pipeline execution
    result = run_analysis_pipeline(
        df,
        file_path,
        insights
    )
    
    return {
        "rows": result["rows"],
        "columns": result["columns"],

        "insights": result["insights"],
        "profile": result["profile"],

        "correlations": result["correlations"],
        "anomaly_details": result["anomaly_details"],

        "dataset_health": result["dataset_health"],
        "conflicts": result["conflicts"],
        "analytical_stability": result["analytical_stability"],

        "ranked_insights": result["ranked_insights"],
        
        "contextual_synthesis": result["contextual_synthesis"],

        "cross_theme_reasoning": result["cross_theme_reasoning"],

        "narrative_summary": result["narrative_summary"],

        "final_insights": result["final_insights"],
        
        "executive_synthesis": result["executive_synthesis"] ,
        
        "recommendations": result["recommendations"] ,

        "chart_path": chart_path
    }