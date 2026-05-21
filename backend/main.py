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
print("STATIC MOUNT ACTIVE")
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
    print("UPLOAD HIT")
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        result = analyze_data(file_path)

        chart_url = None

        if result["chart_path"]:
            chart_url = "/charts/" + os.path.basename(result["chart_path"])

        return {
            "status": "success",
            "data": {
                "file_name": file.filename,
                "summary": {
                    "rows": result["rows"],
                    "columns": result["columns"]
                },
                "insights": result["insights"],
                "chart_url": chart_url
            }
        }

    except Exception as e:
        print("BACKEND ERROR:", repr(e))

        return {
            "status": "error",
            "message": str(e)
        }