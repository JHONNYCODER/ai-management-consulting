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

    result = analyze_data(file_path)

    insights = result["insights"]
    chart_file = result["chart_path"]

    chart_url = None
    if chart_file:
        chart_url = f"/charts/{os.path.basename(chart_file)}"

    summary = {
        "rows": result["rows"],
        "columns": result["columns"]
    }

    return {
        "status": "success",
        "file_name": file.filename,
        "summary": summary,
        "insights": insights,
        "chart_url": chart_url
    }