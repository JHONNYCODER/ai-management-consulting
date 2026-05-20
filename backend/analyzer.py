import pandas as pd
import matplotlib.pyplot as plt
import os

def analyze_data(file_path):
    df = pd.read_csv(file_path)

    insights = []

    # Basic dataset info
    insights.append(f"Dataset contains {len(df)} records.")
    insights.append(f"Dataset contains {len(df.columns)} columns.")

    chart_path = None

    # Salary analysis
    if "Salary" in df.columns:
        plt.figure()
        df["Salary"].dropna().hist()
        plt.title("Salary Distribution")

        chart_path = file_path.replace(".csv", "_salary.png")
        plt.savefig(chart_path)
        plt.close()

        avg_salary = df["Salary"].mean()
        insights.append(f"Average salary is {avg_salary:.2f}.")

    # Performance analysis
    if "PerformanceScore" in df.columns:
        avg_perf = df["PerformanceScore"].mean()

        if avg_perf >= 8:
            insights.append("Overall performance is strong.")
        elif avg_perf >= 6:
            insights.append("Performance is moderate.")
        else:
            insights.append("Performance is weak.")

    return insights, chart_path