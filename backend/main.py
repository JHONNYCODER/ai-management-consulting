from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
import json

from analytics_pipeline.orchestrator import run_pipeline
from analytics_pipeline.config import PipelineConfig
from backend.schemas.analytics_response import AnalyticsResponse
from backend.mappers import map_state_to_api_response

from backend.ai_client import generate_ai_insight

app = FastAPI()

# ─────────────────────────────────────────────
# DIRECTORY & STATIC FILE SETUP
# ─────────────────────────────────────────────
# __file__ is backend/main.py, so dirname is backend/
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Mount only ONCE
app.mount("/charts", StaticFiles(directory=UPLOAD_FOLDER), name="charts")

# ─────────────────────────────────────────────
# MIDDLEWARE
# ─────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────
@app.get("/")
def home():
    return {
        "message": "AI Management Consulting System Running Successfully"
    }

@app.post("/upload", response_model=AnalyticsResponse, response_model_exclude_none=True)
async def upload_file(file: UploadFile = File(...)):
    # 1. Secure the filename to prevent directory traversal attacks
    safe_filename = os.path.basename(file.filename)
    file_path = os.path.join(UPLOAD_FOLDER, safe_filename)

    # 2. Save the file
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File save failed: {str(e)}")

    # 3. Run pipeline and map to API response
    try:
        config = PipelineConfig(output_dir=UPLOAD_FOLDER)
        pipeline_result = run_pipeline(file_path, config=config)
        
        # ✨ INJECT THE AI BRAIN ✨
        if pipeline_result.state.get("llm_payload"):
            ai_narrative = generate_ai_insight(pipeline_result.state["llm_payload"])
            
            raw_ai_text = ai_narrative if isinstance(ai_narrative, str) else str(ai_narrative)
            
            parsed_narrative = raw_ai_text
            clean_exec_summary = "AI analysis completed." # Fallback
            
            try:
                clean_ai = raw_ai_text.strip().replace("```json", "").replace("```", "").strip()
                parsed_narrative = json.loads(clean_ai)
                
                # ✅ EXTRACT CLEAN TEXT FOR EXECUTIVE SUMMARY
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
            pipeline_result.state["executive_synthesis"]["executive_summary"] = clean_exec_summary # ✅ CLEAN TEXT

        # Use our safe mapper instead of manually building the dictionary
        api_response = map_state_to_api_response(pipeline_result.state)
        
        return api_response
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        # 4. Return a proper HTTP error instead of a broken dictionary
        raise HTTPException(status_code=500, detail=f"Pipeline execution failed: {str(e)}")