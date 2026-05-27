import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from analytics_pipeline.logger import logger

# ─────────────────────────────────────────────
# LOAD ENV VARIABLES
# ─────────────────────────────────────────────

load_dotenv() # <-- This loads the .env file automatically!

# ─────────────────────────────────────────────
# AI CLIENTS SETUP
# ─────────────────────────────────────────────

# 1. Groq Cloud Client (Primary)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
groq_client = None
if GROQ_API_KEY:
    groq_client = OpenAI(
        api_key=GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1"
    )

# 2. Ollama Local Client (Fallback)
ollama_client = OpenAI(
    api_key="ollama", # Ollama doesn't need a real key, but the library requires one
    base_url="http://localhost:11434/v1"
)

# ─────────────────────────────────────────────
# AI GENERATION LOGIC
# ─────────────────────────────────────────────

def generate_ai_insight(payload: dict) -> str:
    system_prompt = "You are a business analyst presenting to a non-technical CEO. Ban the following words: 'structural themes', 'reliability decision frame', 'drivers', 'signals', 'moderate'. Use plain English only."
    context = payload.get("context", {})
    recommendations = payload.get("recommendations", {})
    
    context_str = json.dumps(context, indent=2)
    recs_str = json.dumps(recommendations, indent=2)
    
    user_message = (
        f"Here is the analytical context from a dataset:\n{context_str}\n\n"
        f"Here are the initial data-driven recommendations:\n{recs_str}\n\n"
        "CRITICAL INSTRUCTIONS:\n"
        "1. Return ONLY a valid JSON array of exactly 3 objects. No markdown formatting, no extra text, just the raw JSON array.\n"
        "2. Each object must have exactly two keys:\n"
        "   - 'analysis': A simple, jargon-free sentence explaining what the data shows right now.\n"
        "   - 'suggestion': A clear, actionable step on what to do next based on the analysis.\n"
        "Example format:\n"
        '[{"analysis": "Sales dropped 10% last month.", "suggestion": "Renew the expired ad campaign immediately."}]'
    )

    # --- ATTEMPT 1: GROQ (70B Brain) ---
    if groq_client:
        try:
            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=300,
                temperature=0.7
            )
            logger.info("AI insight generated via Groq (70B)")
            return response.choices[0].message.content
        except Exception as e:
            logger.warning(f"Groq failed, falling back to Ollama: {e}")

    # --- ATTEMPT 2: OLLAMA (7B Brain) ---
    try:
        response = ollama_client.chat.completions.create(
            model="qwen2.5:7b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=300,
            temperature=0.7
        )
        logger.info("AI insight generated via Ollama (7B)")
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Ollama also failed: {e}")
        return "[]"