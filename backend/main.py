from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
import json
import uuid
import logging

from analytics_pipeline.orchestrator import run_pipeline
from analytics_pipeline.config import PipelineConfig
from backend.schemas.analytics_response import AnalyticsResponse
from backend.mappers import map_state_to_api_response

from backend.ai_client import generate_ai_insight

# FORCE LOGGING TO PRINT TO TERMINAL
logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

app = FastAPI()

# ─────────────────────────────────────────────
# DIRECTORY & STATIC FILE SETUP
# ─────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
CHART_FOLDER = os.path.join(BASE_DIR, "charts")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CHART_FOLDER, exist_ok=True)

app.mount("/charts", StaticFiles(directory=CHART_FOLDER), name="charts")

# ─────────────────────────────────────────────
# MIDDLEWARE
# ─────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_EXTENSIONS = {".csv", ".tsv", ".xlsx"}
MAX_FILE_SIZE_MB = 50

# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────
@app.get("/")
def home():
    return {"message": "AI Management Consulting System Running Successfully"}

@app.post("/upload", response_model=AnalyticsResponse, response_model_exclude_none=True)
def upload_file(file: UploadFile = File(...)):
    print("\n>>> 1. UPLOAD REQUEST RECEIVED", flush=True)
    
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type {file_ext} not allowed.")

    safe_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(UPLOAD_FOLDER, safe_filename)

    try:
        with open(file_path, "wb") as buffer:
            total_size = 0
            max_size = MAX_FILE_SIZE_MB * 1024 * 1024
            while chunk := file.file.read(1024 * 1024):
                total_size += len(chunk)
                if total_size > max_size:
                    os.remove(file_path)
                    raise HTTPException(status_code=413, detail="File too large.")
                buffer.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File save failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="File upload failed.")

    print(f">>> 2. FILE SAVED TO {file_path}", flush=True)

    try:
        config = PipelineConfig(output_dir=CHART_FOLDER)
        
        print(">>> 3. STARTING PIPELINE...", flush=True)
        pipeline_result = run_pipeline(file_path, config=config)
        print(">>> 4. PIPELINE FINISHED.", flush=True)
        
        if pipeline_result.state.get("llm_payload"):
            print(">>> 5. CALLING AI CLIENT...", flush=True)
            ai_narrative = generate_ai_insight(pipeline_result.state["llm_payload"])
            print(">>> 6. AI CLIENT RETURNED.", flush=True)
            
            raw_ai_text = ai_narrative if isinstance(ai_narrative, str) else str(ai_narrative)
            
            parsed_narrative = raw_ai_text
            clean_exec_summary = "AI analysis completed."
            
            try:
                clean_ai = raw_ai_text.strip()
                if clean_ai.startswith("```"):
                    clean_ai = "\n".join(clean_ai.split("\n")[1:])
                if clean_ai.endswith("```"):
                    clean_ai = clean_ai[:-3]
                clean_ai = clean_ai.strip()
                
                parsed_narrative = json.loads(clean_ai)
                if isinstance(parsed_narrative, list) and len(parsed_narrative) > 0:
                    first_point = parsed_narrative[0]
                    clean_exec_summary = f"{first_point.get('analysis', '')} {first_point.get('suggestion', '')}"
            except (json.JSONDecodeError, AttributeError):
                parsed_narrative = raw_ai_text
                clean_exec_summary = raw_ai_text
            
            if not isinstance(pipeline_result.state.get("narrative_summary"), dict):
                pipeline_result.state["narrative_summary"] = {}
            if not isinstance(pipeline_result.state.get("executive_synthesis"), dict):
                pipeline_result.state["executive_synthesis"] = {}
                
            pipeline_result.state["narrative_summary"]["full_narrative"] = parsed_narrative
            pipeline_result.state["executive_synthesis"]["executive_summary"] = clean_exec_summary

        print(">>> 7. MAPPING STATE TO API RESPONSE...", flush=True)
        api_response = map_state_to_api_response(pipeline_result.state)
        print(">>> 8. RESPONSE MAPPED SUCCESSFULLY. RETURNING.", flush=True)
        
        return api_response
        
    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Pipeline execution failed. Please check server logs.")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)