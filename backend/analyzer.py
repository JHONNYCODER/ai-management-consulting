import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import itertools

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
    """
    Generates a histogram chart for a numeric column
    """
    plt.figure()

    df[column].dropna().hist()

    plt.title(f"{column} Distribution")

    file_name = os.path.basename(file_path).replace(".csv", "_chart.png")

    chart_fs_path = os.path.join("uploads", file_name)

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

    # Dataset quality
    health_score = health.get("health_score", 0)

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
    strongest = None

    if correlations.get("pairs"):
        strongest = max(
            correlations["pairs"],
            key=lambda x: abs(x.get("pearson", 0))
        )

    if strongest:
        strength = abs(strongest.get("pearson", 0))

        if strength >= 0.7:
            summary_parts.append(
                f"There is a strong relationship between {strongest['pair']}."
            )

        elif strength >= 0.4:
            summary_parts.append(
                f"There is a moderate relationship between {strongest['pair']}."
            )

        else:
            summary_parts.append(
                "Relationships between variables are relatively weak."
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
    if correlations and correlations.get("top_correlations"):
        top_strength = correlations["top_correlations"][0]["strength"]

        if top_strength > 0.8 and health_score < 60:
            conflicts.append({
                "type": "correlation_vs_health",
                "severity": "high",
                "message": "Strong correlations exist but dataset quality is low, results may be unreliable"
            })

        elif top_strength > 0.8 and health_score < 80:
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
    if health_score > 80 and not correlations.get("top_correlations"):
        conflicts.append({
            "type": "signal_absence",
            "severity": "low",
            "message": "High-quality dataset but no strong relationships detected"
        })

    return conflicts

def calibrate_confidence(ranked_insights, health, conflicts, df):
    calibrated = []

    health_score = health.get("health_score", 0)
    sample_size = len(df)
    conflict_count = len(conflicts) if conflicts else 0

    for item in ranked_insights:
        confidence = item.get("confidence", "medium")
        score = item.get("score", 0)

        # base numeric mapping
        base_map = {
            "very_high": 1.0,
            "high": 0.75,
            "medium": 0.5,
            "low": 0.25
        }

        adjusted = base_map.get(confidence, 0.5)

        # 🔻 penalty: low dataset quality
        if health_score < 60:
            adjusted *= 0.75

        # 🔻 penalty: small dataset
        if sample_size < 10:
            adjusted *= 0.85

        # 🔻 penalty: conflicting signals
        if conflict_count > 0:
            adjusted *= 0.9

        # re-map back to label
        if adjusted >= 0.85:
            new_confidence = "very_high"
        elif adjusted >= 0.65:
            new_confidence = "high"
        elif adjusted >= 0.4:
            new_confidence = "medium"
        else:
            new_confidence = "low"

        item["confidence"] = new_confidence
        calibrated.append(item)

    return calibrated

def deduplicate_insights(ranked_insights):
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

    suppressed = []

    for item in ranked_insights:
        keep = True

        for c in conflicts:
            if c["type"] == "sample_size_warning":
                # reduce confidence for correlation-heavy insights
                if item["type"] == "correlation":
                    item["confidence"] = "medium"
                    item["priority"] = "medium"

            if c["type"] == "correlation_vs_health":
                if item["type"] == "correlation" and item["score"] > 0.8:
                    item["confidence"] = "medium"

        if keep:
            suppressed.append(item)

    return suppressed

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

def align_contradictions(narrative_summary, ranked_insights, final_insights):
    if not ranked_insights:
        return narrative_summary, final_insights

    # extract strongest signal
    top_signal = ranked_insights[0]
    top_score = top_signal.get("score", 0)
    top_type = top_signal.get("type", "unknown")

    adjusted_narrative = narrative_summary

    # contradiction detection rules
    if top_score < 0.3:
        adjusted_narrative = adjusted_narrative.replace(
            "strong",
            "weak"
        ).replace(
            "high",
            "limited"
        )

    if top_score > 0.7:
        adjusted_narrative = adjusted_narrative.replace(
            "weak",
            "moderate"
        )

    # final insights alignment
    if "summary" in final_insights:
        if top_score < 0.3:
            final_insights["summary"] = (
                "The dataset shows weak and unstable relationships. "
                "Signals are present but not reliable for strong inference."
            )
        elif top_score > 0.7:
            final_insights["summary"] = (
                "The dataset shows strong and consistent statistical relationships. "
                "Patterns are reliable and stable."
            )
        else:
            final_insights["summary"] = (
                "The dataset shows moderate relationships with mixed strength signals."
            )

    return adjusted_narrative, final_insights

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
        final_insights
    )

    return {
        "rows": len(df),
        "columns": len(df.columns),

        "insights": insights,
        "profile": generate_profile(df),

        "correlations": correlations,
        "dataset_health": health,

        "ranked_insights": ranked_insights,
        "conflicts": conflicts,
        "anomaly_details": anomaly_details,

        "narrative_summary": narrative_summary,
        "final_insights": final_insights
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

        results.append({
            "pair": f"{col1} vs {col2}",
            "pearson": round(float(val), 3)
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

def generate_ranked_insights(df, correlations, health, insights):
    ranked = []

    # Health signal
    health_score = health.get("health_score", 0)

    ranked.append({
        "type": "health",
        "priority": "low" if health_score > 70 else "medium",
        "message": "Dataset quality evaluated",
        "score": round(health_score / 100, 3)
    })

    # Correlation signals
    if correlations and "pairs" in correlations:
        for item in correlations["pairs"]:
            strength = abs(item.get("pearson", 0))

            if strength > 0.7:
                priority = "high"
            elif strength > 0.4:
                priority = "medium"
            else:
                priority = "low"

            ranked.append({
                "type": "correlation",
                "priority": priority,
                "message": f"{item['pair']} shows statistical relationship",
                "score": round(strength, 3)
            })

    # Variability signals
    for metric in insights.get("metrics", []):
        if metric["std"] > metric["mean"]:
            ranked.append({
                "type": "variability",
                "priority": "medium",
                "message": f"{metric['column']} shows high variability",
                "score": 0.5
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
    import pandas as pd
    import os

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
        "dataset_health": result["dataset_health"],

        "ranked_insights": result["ranked_insights"],
        "conflicts": result["conflicts"],
        "anomaly_details": result["anomaly_details"],

        "narrative_summary": result["narrative_summary"],
        "final_insights": result["final_insights"],

        "chart_path": chart_path
    }