import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import itertools


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

            results.append({
                "pair": f"{col1} vs {col2}",
                "pearson": round(float(pearson_val), 3),
                "spearman": round(float(spearman_val), 3),
                "strength": round(abs(pearson_val), 3)
            })

        # sort by strongest linear relationship
        results.sort(key=lambda x: x["strength"], reverse=True)

        return {
            "total_pairs": len(results),
            "top_correlations": results[:10]
        }
        print("PROFILE:", generate_profile(df))
        print("CORRELATIONS:", generate_correlation_analysis(df))

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


    return {
        "rows": len(df),
        "columns": len(df.columns),
        "insights": insights,
        "profile": generate_profile(df),
        "correlations": generate_correlation_analysis(df),
        "chart_path": chart_path
    }