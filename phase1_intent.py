import os
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def parse_relative_time(text: str, base_time: Optional[datetime] = None) -> Optional[datetime]:
    """
    Parses relative expressions like 'in 10 minutes', 'in 2 hours', 
    or absolute times like 'at 5:30 PM', 'tomorrow at 9am'.
    """
    now = base_time or datetime.now(timezone.utc)
    lower = text.lower()

    # Pattern 1: 'in X minute(s) / second(s) / hour(s)'
    rel_match = re.search(r'in\s+(\d+)\s*(min|minute|minutes|hour|hours|sec|second|seconds|day|days)', lower)
    if rel_match:
        qty = int(rel_match.group(1))
        unit = rel_match.group(2)
        if "sec" in unit:
            return now + timedelta(seconds=qty)
        elif "min" in unit:
            return now + timedelta(minutes=qty)
        elif "hour" in unit:
            return now + timedelta(hours=qty)
        elif "day" in unit:
            return now + timedelta(days=qty)

    # Pattern 2: 'at HH:MM AM/PM' or 'at HH AM/PM'
    time_match = re.search(r'at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', lower)
    if time_match:
        hours = int(time_match.group(1))
        mins = int(time_match.group(2)) if time_match.group(2) else 0
        meridiem = time_match.group(3)

        if meridiem == "pm" and hours < 12:
            hours += 12
        elif meridiem == "am" and hours == 12:
            hours = 0

        target = now.replace(hour=hours, minute=mins, second=0, microsecond=0)
        # If the target hour is already in the past today, schedule it for tomorrow
        if target <= now:
            target += timedelta(days=1)
        return target

    # Default fallback: 10 minutes from now
    return now + timedelta(minutes=10)

def parse_user_intent(user_text: str, now: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Parses natural language user commands into structured intent data.
    Intent types: 'CREATE', 'DELETE', 'QUERY', 'UNKNOWN'
    """
    current_time = now or datetime.now(timezone.utc)
    clean_text = user_text.strip()
    lower_text = clean_text.lower()

    # 1. Detection of CANCELLATION / DELETION intents
    cancel_words = ["cancel", "delete", "remove", "dismiss", "stop", "clear"]
    if any(lower_text.startswith(w) or f" {w} " in f" {lower_text} " for w in cancel_words):
        is_all = any(term in lower_text for term in ["all", "everything", "all alarms", "all reminders"])
        target_task = re.sub(r'^(cancel|delete|remove|dismiss|stop|clear)\s+(the\s+|my\s+)?', '', clean_text, flags=re.IGNORECASE).strip()
        
        return {
            "intent": "DELETE",
            "task_name": "All Alarms" if is_all else (target_task or "Alarm"),
            "target_time_iso": current_time.isoformat(),
            "friendly_response": f"Canceled {'all alarms' if is_all else target_task or 'alarm'}.",
            "model_used": "heuristics-parser",
            "is_all": is_all
        }

    # 2. Detection of QUERY / LIST intents
    query_words = ["what alarms", "list alarms", "show reminders", "what are my reminders", "any alarms"]
    if any(q in lower_text for q in query_words):
        return {
            "intent": "QUERY",
            "task_name": "List Alarms",
            "target_time_iso": current_time.isoformat(),
            "friendly_response": "Checking your active alarms.",
            "model_used": "heuristics-parser"
        }

    # 3. CREATE Reminder intent
    target_dt = parse_relative_time(clean_text, current_time)
    
    # Extract clean task name by stripping common prefixes
    task = re.sub(
        r'^(remind me to|set an alarm for|set alarm for|set a reminder to|create a reminder to|alarm for|remind me)\s*',
        '',
        clean_text,
        flags=re.IGNORECASE
    )
    # Strip trailing relative/time clauses from the task title
    task = re.sub(r'\s+(in\s+\d+\s*(mins?|minutes?|hours?|secs?|seconds?)|at\s+\d{1,2}(:\d{2})?\s*(am|pm)?).*$', '', task, flags=re.IGNORECASE).strip()
    if not task:
        task = "Voice Reminder"

    return {
        "intent": "CREATE",
        "task_name": task,
        "target_time_iso": target_dt.isoformat(),
        "friendly_response": f"Set alarm for '{task}' at {target_dt.strftime('%I:%M %p')}.",
        "model_used": "heuristics-parser"
    }

if __name__ == "__main__":
    test_phrases = [
        "Remind me to study AWS in 15 minutes",
        "Set an alarm for Team Standup at 3:30 PM",
        "Cancel the AWS alarm",
        "Cancel all alarms",
        "What are my reminders?"
    ]
    print("=== Testing Intent Engine ===")
    for phrase in test_phrases:
        result = parse_user_intent(phrase)
        print(f"\nUser: '{phrase}'")
        print(f"-> Intent: {result['intent']} | Task: '{result['task_name']}' | Time: {result['target_time_iso']}")