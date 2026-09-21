import os
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import database
from phase1_intent import parse_user_intent

# Initialize FastAPI application
app = FastAPI(
    title="Voice Alarm & Reminder Engine",
    description="Full-stack voice-to-alarm scheduler with NLP intent recognition and SQLite persistence.",
    version="1.0.0"
)

# Enable CORS for browser frontends (Vite, React, or static HTML)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------- Pydantic Models -----------------

class VoiceParseRequest(BaseModel):
    text: str

class VoiceParseResponse(BaseModel):
    intent: str
    task_name: str
    target_time_iso: str
    friendly_response: str
    model_used: str
    created_id: Optional[int] = None

class ManualReminderCreate(BaseModel):
    task_name: str
    reminder_time_iso: str

class ReminderItem(BaseModel):
    id: int
    task_name: str
    reminder_time: str
    status: str
    created_at: str

# ----------------- Lifecycle Events -----------------

@app.on_event("startup")
def startup_event():
    database.init_db()

# ----------------- REST Endpoints -----------------

@app.get("/api/health")
def health_check():
    """Health check endpoint to verify backend status."""
    return {
        "status": "healthy",
        "service": "voice-alarm-scheduler",
        "time": datetime.now(timezone.utc).isoformat()
    }

@app.get("/api/reminders", response_model=List[ReminderItem])
def list_reminders():
    """Returns all reminders currently stored in SQLite."""
    return database.get_all_reminders()

@app.post("/api/reminders", status_code=status.HTTP_201_CREATED)
def create_reminder_manual(payload: ManualReminderCreate):
    """Directly insert a reminder with explicit task name and ISO timestamp."""
    new_id = database.insert_reminder(payload.task_name, payload.reminder_time_iso)
    return {
        "success": True,
        "id": new_id,
        "task_name": payload.task_name,
        "reminder_time": payload.reminder_time_iso
    }

@app.post("/api/voice-parse", response_model=VoiceParseResponse)
def handle_voice_input(payload: VoiceParseRequest):
    """
    Parses natural language speech text, identifies intent (CREATE, DELETE, QUERY),
    and executes database operations automatically.
    """
    if not payload.text or not payload.text.strip():
        raise HTTPException(status_code=400, detail="Voice text input cannot be empty.")

    intent_result = parse_user_intent(payload.text)
    intent = intent_result["intent"]
    created_id = None

    if intent == "CREATE":
        created_id = database.insert_reminder(
            task_name=intent_result["task_name"],
            reminder_time_iso=intent_result["target_time_iso"]
        )
    elif intent == "DELETE":
        if intent_result.get("is_all"):
            count = database.delete_all_reminders(active_only=True)
            intent_result["friendly_response"] = f"Canceled {count} active alarm(s)."
        else:
            deleted = database.cancel_reminder_by_query(intent_result["task_name"])
            if deleted:
                intent_result["friendly_response"] = f"Canceled alarm '{deleted['task_name']}'."
            else:
                intent_result["friendly_response"] = f"No active alarm found matching '{intent_result['task_name']}'."

    return {
        "intent": intent,
        "task_name": intent_result["task_name"],
        "target_time_iso": intent_result["target_time_iso"],
        "friendly_response": intent_result["friendly_response"],
        "model_used": intent_result["model_used"],
        "created_id": created_id
    }

@app.delete("/api/reminders/{reminder_id}")
def delete_single_reminder(reminder_id: int):
    """Deletes a reminder by ID."""
    success = database.delete_reminder(reminder_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Reminder ID {reminder_id} not found.")
    return {"success": True, "deleted_id": reminder_id}

@app.post("/api/reminders/cancel-all")
def cancel_all_active_reminders():
    """Cancels/deletes all active alarms in SQLite."""
    count = database.delete_all_reminders(active_only=True)
    return {"success": True, "count": count, "message": f"Successfully canceled {count} active alarm(s)."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)