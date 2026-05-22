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


def generate_profile(df):
        profile = {}

        for col in df.columns:
            # skip ID-like columns
            if "id" in col.lower():
                continue

            series = df[col].dropna()
            col_type = detect_column_type(series)

            if col_type == "numeric":
                profile[col] = profile_numeric_column(series)
            else:
                profile[col] = profile_categorical_column(series)

        return profile
    
def generate_correlation_analysis(df):
    numeric_df = df.select_dtypes(include=[np.number])

    if numeric_df.shape[1] < 2:
        return {
            "message": "Not enough numeric columns for correlation"
        }

    pearson_corr = numeric_df.corr(method="pearson")
    spearman_corr = numeric_df.corr(method="spearman")

    results = []
    columns = numeric_df.columns

    for col1, col2 in itertools.combinations(columns, 2):
        pearson_val = pearson_corr.loc[col1, col2]
        spearman_val = spearman_corr.loc[col1, col2]

        abs_val = abs(pearson_val)

       
        # stronger filtering of weak correlations
        if abs_val < 0.4:
            continue

        if "id" in col1.lower() or "id" in col2.lower():
            continue

        results.append({
            "pair": f"{col1} vs {col2}",
            "pearson": round(float(pearson_val), 3),
            "spearman": round(float(spearman_val), 3),
            "strength": round(abs_val, 3)
        })

    results.sort(key=lambda x: x["strength"], reverse=True)

    return {
        "total_pairs": len(results),
        "top_correlations": results[:10]
    }

def generate_dataset_health(df):
    report = {}

    # 1. Missing value ratio
    missing_ratio = df.isnull().sum().sum() / (df.shape[0] * df.shape[1])

    completeness_score = max(0, 1 - missing_ratio)

    # 2. Numeric anomaly detection (z-score)
    numeric_df = df.select_dtypes(include=[np.number])

    anomaly_count = 0

    for col in numeric_df.columns:
        series = numeric_df[col].dropna()

        if len(series) < 3:
            continue

        mean = series.mean()
        std = series.std()

        if std == 0:
            continue

        z_scores = (series - mean) / std
        anomaly_count += (abs(z_scores) > 3).sum()

    # 3. Categorical dominance check
    categorical_df = df.select_dtypes(exclude=[np.number])

    dominance_issues = 0

    for col in categorical_df.columns:
        top_freq = df[col].value_counts(normalize=True).iloc[0]
        if top_freq > 0.8:
            dominance_issues += 1

    # 4. Score calculation (simple weighted model)
    health_score = (
        completeness_score * 0.4 +
        max(0, 1 - anomaly_count / (len(df) + 1)) * 0.4 +
        max(0, 1 - dominance_issues / (len(categorical_df.columns) + 1)) * 0.2
    ) * 100

    return {
        "completeness_score": round(completeness_score, 3),
        "anomaly_count": int(anomaly_count),
        "dominance_issues": int(dominance_issues),
        "health_score": round(health_score, 2)
    }

def generate_narrative_summary(df, correlations, health):
    parts = []

    # 1. Dataset health interpretation
    score = health.get("health_score", 0)

    if score >= 80:
        parts.append("The dataset is high quality with minimal structural issues.")
    elif score >= 60:
        parts.append("The dataset is moderately clean with some quality concerns.")
    else:
        parts.append("The dataset has noticeable quality issues that may affect reliability.")

    # 2. Correlation insight
    if correlations and "top_correlations" in correlations and correlations["top_correlations"]:
        top = correlations["top_correlations"][0]
        pair = top["pair"]
        strength = top["strength"]

        if strength >= 0.8:
            parts.append(f"There is a strong relationship between {pair}, indicating a clear dependency pattern.")
        elif strength >= 0.5:
            parts.append(f"There is a moderate relationship between {pair}, suggesting partial dependency.")
        else:
            parts.append(f"Relationships between variables are weak and not strongly predictive.")

    # 3. Dataset structure insight
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    categorical_cols = df.select_dtypes(exclude=[np.number]).columns

    parts.append(
        f"The dataset contains {len(numeric_cols)} numeric and {len(categorical_cols)} categorical features."
    )

    return " ".join(parts)

def generate_ranked_insights(df, correlations, health, insights):
    ranked = []

    # 1. Correlation-based insights
    if correlations and "top_correlations" in correlations:
        for item in correlations["top_correlations"]:
            strength = item["strength"]
            
            if strength >= 0.8:
                priority = "high"
            elif strength >= 0.5:
                priority = "medium"
            else:
                priority = "low"

            if strength >= 0.8:
                confidence = "very_high"
            elif strength >= 0.6:
                confidence = "high"
            elif strength >= 0.4:
                confidence = "medium"
            else:
                confidence = "low"

            ranked.append({
                "type": "correlation",
                "priority": priority,
                "message": f"{item['pair']} shows statistical relationship",
                "score": round(strength, 3),
                "confidence": confidence
            })

    # 2. Dataset health insights
    health_score = health.get("health_score", 0)

    if health_score >= 80:
        priority = "low"
    elif health_score >= 60:
        priority = "medium"
    else:
        priority = "high"

    ranked.append({
        "type": "health",
        "priority": priority,
        "message": "Overall dataset quality evaluated",
        "score": round(health_score / 100, 3)
    })

    # 3. Variability insights from metrics
    for metric in insights.get("metrics", []):
        if metric["std"] > metric["mean"]:
            ranked.append({
                "type": "variability",
                "priority": "medium",
                "message": f"{metric['column']} shows high variability",
                "score": 0.6
            })

    # Sort by score
    ranked.sort(key=lambda x: x["score"], reverse=True)

    return ranked[:10]

def generate_anomaly_explanations(df):
    numeric_df = df.select_dtypes(include=[np.number])

    anomalies = []

    for col in numeric_df.columns:
        series = numeric_df[col].dropna()

        if len(series) < 3:
            continue

        mean = series.mean()
        std = series.std()

        if std == 0:
            continue

        z_scores = (series - mean) / std

        for idx, z in z_scores.items():
            if abs(z) > 3:
                severity = "high" if abs(z) > 4 else "medium"

                anomalies.append({
                    "column": col,
                    "row_index": int(idx),
                    "value": float(series.loc[idx]),
                    "z_score": round(float(z), 3),
                    "severity": severity,
                    "reason": "statistical_outlier_z_score"
                })

    # sort most extreme first
    anomalies.sort(key=lambda x: abs(x["z_score"]), reverse=True)

    return anomalies[:20]

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

def generate_final_insights(rankings, conflicts, narrative):
    key_findings = []
    warnings = []
    supporting = []

    # 1. Pull high priority ranked insights
    for item in rankings:
        if item["priority"] == "high":
            key_findings.append(item["message"])
        elif item["priority"] == "medium":
            supporting.append(item["message"])

    # 2. Add conflicts as warnings
    for c in conflicts:
        warnings.append(c["message"])

    # 3. Compress narrative (keep it as base summary)
    summary = narrative

    return {
        "key_findings": key_findings[:5],
        "supporting_evidence": supporting[:5],
        "warnings": warnings[:5],
        "summary": summary
    }

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

def analyze_data(file_path):
    """
    Clean pipeline:
    - Load CSV
    - Detect numeric columns
    - Generate summary + metrics
    - Create chart
    - Return JSON-safe response
    """

    df = pd.read_csv(file_path)

    if df.empty:
        return {
            "status": "error",
            "message": "CSV file is empty.",
            "rows": 0,
            "columns": 0,
            "insights": {
                "summary": [],
                "metrics": []
            },
            "chart_path": None
        }
    insights = {
        "summary": [],
        "metrics": []
    }
    # Convert columns to numeric where possible
    numeric_columns = df.select_dtypes(include=[np.number]).columns.tolist()

    # Detect numeric columns
    numeric_columns = [
        col for col in df.columns
        if pd.api.types.is_numeric_dtype(df[col])
    ]

    # Generate metrics  
    for column in numeric_columns:
        series = df[column].dropna()

        if series.empty:
            continue

        mean_val = series.mean()
        median_val = series.median()
        std_val = series.std()
        min_val = series.min()
        max_val = series.max()

        insights["metrics"].append({
            "column": column,
            "mean": round(float(mean_val), 2),
            "median": round(float(median_val), 2),
            "std": round(float(std_val), 2),
            "min": round(float(min_val), 2),
            "max": round(float(max_val), 2)
        })

        # basic insight layer
        if std_val / (mean_val + 1e-9) > 1:
            insights["summary"].append(f"{column} shows high variability")
        elif std_val / (mean_val + 1e-9) < 0.2:
            insights["summary"].append(f"{column} is relatively stable")
    
    # Chart generation

    chart_path = None

    if numeric_columns is not None and len(numeric_columns) > 0:
        try:
            chart_path = generate_chart(df, numeric_columns[0], file_path)
        except Exception as e:
            print("Chart generation failed:", e)
            chart_path = None   

    # =========================
    # Core Analysis Hooks
    # =========================

    health = generate_dataset_health(df)

    correlations = generate_correlation_analysis(df)

    conflicts = generate_conflict_detection(
        correlations,
        health,
        df
    )

    anomaly_details = generate_anomaly_explanations(df)


    # =========================
    # Insight Generation Layer
    # =========================

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

    ranked_insights = resolve_conflicts(conflicts, ranked_insights)

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


    # =========================
    # Narrative + Final Layer
    # =========================

    narrative_summary = generate_narrative_summary(
        df,
        correlations,
        health
    )

    final_insights = generate_final_insights(
        ranked_insights,
        conflicts,
        narrative_summary
    )


    # =========================
    # ALIGNMENT LAYER (STEP 18 FIX)
    # =========================

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
        "chart_path": chart_path,
        "dataset_health": generate_dataset_health(df),
        "ranked_insights": ranked_insights,
        "conflicts": conflicts,
        "anomaly_details": anomaly_details,
        "narrative_summary": generate_narrative_summary(
            df,
            correlations,
            health
        ),
        "final_insights": final_insights,
    }