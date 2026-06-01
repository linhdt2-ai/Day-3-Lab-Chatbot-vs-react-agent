import os
import json
import glob
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Load environment variables
from dotenv import load_dotenv
load_dotenv(override=True)

from src.core.openai_provider import OpenAIProvider
from src.core.gemini_provider import GeminiProvider
from src.core.local_provider import LocalProvider
from src.agent.agent import ReActAgent
from src.tools.vinwonders_tools import available_tools
from src.telemetry.logger import logger

app = FastAPI(title="VinWonders Nam Hội An AI Assistant")

# Ensure static and logs directories exist
os.makedirs("src/static", exist_ok=True)
os.makedirs("logs", exist_ok=True)

HISTORY_FILE = "logs/chat_history.json"

def load_history() -> Dict[str, Any]:
    if not os.path.exists(HISTORY_FILE):
        return {}
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_history(history: Dict[str, Any]):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save chat history: {e}")

# API Models
class ChatRequest(BaseModel):
    message: str
    session_id: str
    provider: str = "google" # google | openai | local
    mode: str = "react"      # react | baseline

# Endpoints
@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    """
    Handles conversation requests. Evaluates if baseline or ReAct Agent,
    executes the system, records logs, and updates persistent history.
    """
    message = req.message.strip()
    session_id = req.session_id.strip()
    provider_name = req.provider.strip().lower()
    mode = req.mode.strip().lower()

    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    if not session_id:
        raise HTTPException(status_code=400, detail="Session ID is required")

    # 1. Initialize LLM Provider based on config
    llm = None
    try:
        if provider_name == "google":
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("GEMINI_API_KEY is not configured in .env file.")
            default_model = os.getenv("DEFAULT_MODEL", "gemini-2.5-flash")
            llm = GeminiProvider(model_name=default_model, api_key=api_key)
            
        elif provider_name == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY is not configured in .env file.")
            llm = OpenAIProvider(model_name="gpt-4o", api_key=api_key)
            
        elif provider_name == "local":
            model_path = os.getenv("LOCAL_MODEL_PATH", "./models/Phi-3-mini-4k-instruct-q4.gguf")
            if not os.path.exists(model_path):
                raise ValueError(f"Local model not found at {model_path}. Please place your GGUF model there.")
            llm = LocalProvider(model_path=model_path)
            
        else:
            raise ValueError(f"Unknown provider: {provider_name}")
            
    except Exception as ex:
        logger.error(f"LLM Provider Initialization Error: {ex}")
        raise HTTPException(status_code=500, detail=str(ex))

    # 2. Run Chatbot / Agent
    agent = ReActAgent(llm=llm, tools=available_tools, max_steps=5)
    
    if mode == "baseline":
        result = agent.run_baseline(message)
    else:
        result = agent.run(message)

    # 3. Save to History
    history = load_history()
    if session_id not in history:
        history[session_id] = {
            "title": message[:30] + ("..." if len(message) > 30 else ""),
            "created_at": datetime.utcnow().isoformat(),
            "messages": []
        }
        
    history[session_id]["messages"].append({
        "role": "user",
        "content": message,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    history[session_id]["messages"].append({
        "role": "assistant",
        "content": result["answer"],
        "trace": result["trace"],
        "metrics": result["metrics"],
        "mode": mode,
        "provider": provider_name,
        "timestamp": datetime.utcnow().isoformat()
    })
    save_history(history)

    return result

@app.get("/api/history")
async def get_history_sessions():
    """Lists all historical sessions for the sidebar."""
    history = load_history()
    sessions = []
    for sid, info in history.items():
        sessions.append({
            "session_id": sid,
            "title": info.get("title", "Lịch sử chat"),
            "created_at": info.get("created_at")
        })
    # Sort by created_at descending
    sessions.sort(key=lambda x: x["created_at"] or "", reverse=True)
    return sessions

@app.get("/api/history/{session_id}")
async def get_session_messages(session_id: str):
    """Retrieves full messages of a specific session."""
    history = load_history()
    if session_id not in history:
        raise HTTPException(status_code=404, detail="Session not found")
    return history[session_id]["messages"]

@app.delete("/api/history/{session_id}")
async def delete_session(session_id: str):
    """Deletes a specific session."""
    history = load_history()
    if session_id in history:
        del history[session_id]
        save_history(history)
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Session not found")

@app.delete("/api/history")
async def clear_all_history():
    """Clears all persistent chat histories."""
    save_history({})
    return {"status": "cleared"}

@app.get("/api/dashboard")
async def get_dashboard_metrics():
    """
    Parses structural JSON log files written in the logs/ folder,
    aggregates stats (Total Chats, Latency, Errors, Tool Usage, Costs)
    and serves it to the frontend analytics dashboard.
    """
    total_chats = 0
    total_latency_ms = 0
    success_count = 0
    fallback_count = 0
    error_count = 0
    
    total_prompt_tokens = 0
    total_completion_tokens = 0
    estimated_cost = 0.0
    
    tool_usage = {}
    
    # Read telemetry logs from directory
    log_files = glob.glob("logs/*.log")
    for log_path in log_files:
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        entry = json.loads(line)
                        event = entry.get("event")
                        data = entry.get("data", {})
                        
                        if event == "AGENT_START":
                            total_chats += 1
                        elif event == "AGENT_END":
                            status = data.get("status")
                            latency = data.get("latency_ms", 0)
                            total_latency_ms += latency
                            
                            if status == "success":
                                success_count += 1
                            elif status == "fallback":
                                fallback_count += 1
                            else:
                                error_count += 1
                        elif event == "AGENT_STEP_COMPLETE":
                            step_type = data.get("type")
                            if step_type == "tool_call":
                                tool = data.get("tool", "Unknown")
                                tool_usage[tool] = tool_usage.get(tool, 0) + 1
                        elif event == "LLM_METRIC":
                            total_prompt_tokens += data.get("prompt_tokens", 0)
                            total_completion_tokens += data.get("completion_tokens", 0)
                            estimated_cost += data.get("cost_estimate", 0.0)
                        elif event == "AGENT_PARSER_ERROR" or event == "AGENT_LOOP_DETECTED":
                            error_count += 1
                            
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Error reading log file {log_path}: {e}")

    # Fallback checking if logs are empty (use session history if logs are new)
    history = load_history()
    if total_chats == 0 and history:
        for sid, sinfo in history.items():
            for msg in sinfo.get("messages", []):
                if msg.get("role") == "assistant":
                    total_chats += 1
                    metrics = msg.get("metrics", {})
                    total_latency_ms += metrics.get("latency_ms", 0)
                    total_prompt_tokens += metrics.get("tokens", 0)
                    
                    status = metrics.get("status", "success")
                    if status == "success":
                        success_count += 1
                    elif status == "fallback":
                        fallback_count += 1
                    else:
                        error_count += 1
                        
                    trace = msg.get("trace", [])
                    for step in trace:
                        action = step.get("action", "")
                        if "(" in action:
                            tname = action.split("(")[0].strip()
                            tool_usage[tname] = tool_usage.get(tname, 0) + 1

    avg_latency = (total_latency_ms / max(success_count + fallback_count, 1)) / 1000.0 # to seconds
    total_runs = success_count + fallback_count + error_count
    success_rate = (success_count / max(total_runs, 1)) * 100.0
    
    # Fill in default tool usage if empty for nice chart rendering
    for t in available_tools:
        if t["name"] not in tool_usage:
            tool_usage[t["name"]] = 0

    return {
        "total_chats": total_chats,
        "success_rate": round(success_rate, 1),
        "avg_latency_s": round(avg_latency, 2),
        "total_tokens": total_prompt_tokens + total_completion_tokens,
        "estimated_cost_usd": round(estimated_cost, 5),
        "success_count": success_count,
        "fallback_count": fallback_count,
        "error_count": error_count,
        "tool_usage": tool_usage
    }

# Serving single-page UI assets
@app.get("/")
async def root():
    index_path = "src/static/index.html"
    if not os.path.exists(index_path):
        return HTMLResponse("<h2>UI index.html not found yet. Please create it under src/static/</h2>")
    return FileResponse(index_path)

# Mount static folder
app.mount("/", StaticFiles(directory="src/static"), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.app:app", host="0.0.0.0", port=8000, reload=True)