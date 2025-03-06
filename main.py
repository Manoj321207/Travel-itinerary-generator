import os
from typing import Optional
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import httpx
from pydantic import BaseModel
import json
from prompt_templates import TRAVEL_ITINERARY_PROMPT, DESTINATION_DESCRIPTION_PROMPT

app = FastAPI(title="Travel Itinerary Generator")

# Set up templates and static files
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configuration for API
WEBUI_ENABLED = True  
WEBUI_BASE_URL = "https://chat.ivislabs.in/api"
API_KEY = "sk-2f66f2c0eebd42b29b3e0d712f98f564"  
DEFAULT_MODEL = "gemma2:2b"  

OLLAMA_ENABLED = True  
OLLAMA_HOST = "localhost"
OLLAMA_PORT = "11434"
OLLAMA_API_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}/api"

class ItineraryRequest(BaseModel):
    destination: str
    duration: int
    interests: str
    budget: Optional[str] = "moderate"
    travel_style: Optional[str] = "adventurous"

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/generate_itinerary")
async def generate_itinerary(
    destination: str = Form(...),
    duration: int = Form(...),
    interests: str = Form(...),
    budget: str = Form("moderate"),
    travel_style: str = Form("adventurous"),
    model: str = Form(DEFAULT_MODEL)
):
    try:
        # Build the prompt
        prompt = TRAVEL_ITINERARY_PROMPT.format(
            destination=destination,
            duration=duration,
            interests=interests,
            budget=budget,
            travel_style=travel_style
        )

        generated_text = await query_llm_api(prompt, model)
        # print(f"Generated Itinerary: {generated_text}")  # Debugging line

        return {"generated_itinerary": generated_text}

    except Exception as e:
        print(f"Error generating itinerary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating itinerary: {str(e)}")

@app.post("/generate_description")
async def generate_description(
    destination: str = Form(...),
    interests: str = Form(...),
    model: str = Form(DEFAULT_MODEL)
):
    try:
        # Build the prompt
        prompt = DESTINATION_DESCRIPTION_PROMPT.format(
            destination=destination,
            interests=interests
        )

        generated_text = await query_llm_api(prompt, model)
        return {"generated_description": generated_text}

    except Exception as e:
        print(f"Error generating description: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating description: {str(e)}")

async def query_llm_api(prompt: str, model: str):
    """Handles API calls to Open-WebUI or Ollama for generating content."""
    try:
        if WEBUI_ENABLED:
            try:
                messages = [{"role": "user", "content": prompt}]
                request_payload = {"model": model, "messages": messages}

                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{WEBUI_BASE_URL}/chat/completions",
                        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                        json=request_payload,
                        timeout=60.0
                    )

                    if response.status_code == 200:
                        result = response.json()
                        return extract_response_text(result)

            except Exception as e:
                print(f"Open-webui API failed: {str(e)}")

        if OLLAMA_ENABLED:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{OLLAMA_API_URL}/generate",
                    json={"model": model, "prompt": prompt, "stream": False},
                    timeout=60.0
                )

                if response.status_code == 200:
                    result = response.json()
                    return result.get("response", "")

        raise HTTPException(status_code=500, detail="Failed to generate content from any available API")

    except Exception as e:
        print(f"API query error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"API query error: {str(e)}")

def extract_response_text(api_response):
    """Extracts the generated text from different API response formats."""
    if "choices" in api_response and len(api_response["choices"]) > 0:
        choice = api_response["choices"][0]
        if "message" in choice and "content" in choice["message"]:
            return choice["message"]["content"]
        elif "text" in choice:
            return choice["text"]
    elif "response" in api_response:
        return api_response["response"]
    return ""

@app.get("/models")
async def get_models():
    try:
        if WEBUI_ENABLED:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{WEBUI_BASE_URL}/models", headers={"Authorization": f"Bearer {API_KEY}"})
                if response.status_code == 200:
                    models_data = response.json()
                    if "data" in models_data and isinstance(models_data["data"], list):
                        model_names = [model["id"] for model in models_data["data"] if "id" in model]
                        return {"models": model_names}

        if OLLAMA_ENABLED:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{OLLAMA_API_URL}/tags")
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    model_names = [model.get("name") for model in models]
                    return {"models": model_names}

        return {"models": [DEFAULT_MODEL, "gemma2:2b", "qwen2.5:0.5b", "deepseek-r1:1.5b", "deepseek-coder:latest"]}

    except Exception as e:
        print(f"Unexpected error in get_models: {str(e)}")
        return {"models": [DEFAULT_MODEL]}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
