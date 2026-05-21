import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os

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

    return f"charts/{file_name}"


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

    if numeric_columns:
        chart_path = generate_chart(df, numeric_columns[0], file_path)

    return {
        "status": "success",
        "rows": len(df),
        "columns": len(df.columns),
        "insights": insights,
        "chart_path": chart_path
    }