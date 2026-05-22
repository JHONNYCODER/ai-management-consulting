from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, UploadFile, File
import pandas as pd
import matplotlib.pyplot as plt
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os

from analyzer import analyze_data

app = FastAPI()

app.mount("/charts", StaticFiles(directory="uploads"), name="charts")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_FOLDER = "uploads"

@app.get("/")
def home():
    return {
        "message": "AI Management Consulting System Running Successfully"
    }

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
   
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        result = analyze_data(file_path)

        chart_url = None

        chart_path = result.get("chart_path") or result.get("chart_url")

        chart_url = None
        if chart_path:
            chart_url = "/charts/" + os.path.basename(chart_path)
        print("MAIN.PY KEYS:", result.keys())
        return {
            "status": "success",
            "data": {
                "file_name": file.filename,

                "summary": {
                    "rows": result.get("rows"),
                    "columns": result.get("columns")
                },

                "insights": result.get("insights"),
                "profile": result.get("profile"),
                "correlations": result.get("correlations"),
                "anomaly_details": result.get("anomaly_details"),

                "dataset_health": result.get("dataset_health"),
                "analytical_stability": result.get("analytical_stability"),
                "conflicts": result.get("conflicts"),

                "ranked_insights": result.get("ranked_insights"),
               
                "contextual_synthesis": result.get("contextual_synthesis", {}),
               
                "cross_theme_reasoning": result.get('cross_theme_reasoning') ,
               
                "narrative_summary": result.get("narrative_summary"),

                "final_insights": result.get("final_insights"),

                "executive_synthesis" : result.get("executive_synthesis"),

                "recommendations" : result.get("recommendations"),


                "chart_url": (
                    "/charts/" + os.path.basename(result["chart_path"])
                    if result.get("chart_path")
                    else None
                )
            }
        }

    except Exception as e:
        import traceback
        traceback.print_exc()

        return {
            "status": "error",
            "message": str(e)
        }