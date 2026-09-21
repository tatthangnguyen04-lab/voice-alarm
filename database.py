import sqlite3
from datetime import datetime, timezone
from typing import List, Dict, Optional

DB_NAME = "reminders.db"

def get_connection():
    """Returns a SQLite connection configured with dict-like row access."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Creates the reminders table if it doesn't already exist."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_name TEXT NOT NULL,
                reminder_time TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                created_at TEXT NOT NULL
            );
        """)
        conn.commit()
    print(f"[*] SQLite Database initialized at '{DB_NAME}'")

def insert_reminder(task_name: str, reminder_time_iso: str) -> int:
    """Inserts a new reminder and returns its auto-incremented ID."""
    with get_connection() as conn:
        cursor = conn.cursor()
        created_at = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            """
            INSERT INTO reminders (task_name, reminder_time, status, created_at)
            VALUES (?, ?, 'ACTIVE', ?)
            """,
            (task_name, reminder_time_iso, created_at)
        )
        conn.commit()
        return cursor.lastrowid

def get_all_reminders() -> List[Dict]:
    """Retrieves all reminders ordered by reminder_time."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM reminders ORDER BY reminder_time ASC")
        return [dict(row) for row in cursor.fetchall()]

def get_due_reminders(now_iso: str) -> List[Dict]:
    """Retrieves all active reminders whose scheduled time is <= now."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM reminders 
            WHERE status = 'ACTIVE' AND reminder_time <= ?
            ORDER BY reminder_time ASC
            """,
            (now_iso,)
        )
        return [dict(row) for row in cursor.fetchall()]

def update_reminder_status(reminder_id: int, status: str) -> bool:
    """Updates the status of a reminder (e.g. 'COMPLETED', 'DISMISSED')."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE reminders SET status = ? WHERE id = ?",
            (status, reminder_id)
        )
        conn.commit()
        return cursor.rowcount > 0

def delete_reminder(reminder_id: int) -> bool:
    """Deletes a reminder by ID."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
        conn.commit()
        return cursor.rowcount > 0

def delete_all_reminders(active_only: bool = True) -> int:
    """Cancels/deletes reminders in bulk."""
    with get_connection() as conn:
        cursor = conn.cursor()
        if active_only:
            cursor.execute("DELETE FROM reminders WHERE status = 'ACTIVE'")
        else:
            cursor.execute("DELETE FROM reminders")
        conn.commit()
        return cursor.rowcount

def cancel_reminder_by_query(query: str) -> Optional[Dict]:
    """Fuzzy-matches active alarms by task name or keyword and cancels them."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM reminders WHERE status = 'ACTIVE' ORDER BY reminder_time ASC")
        rows = [dict(r) for r in cursor.fetchall()]

    if not rows:
        return None

    clean = query.lower().strip()
    # 1. Exact or substring match
    for r in rows:
        if clean in r["task_name"].lower() or r["task_name"].lower() in clean:
            delete_reminder(r["id"])
            return r

    # 2. Keyword match
    words = [w for w in clean.split() if len(w) > 2]
    for r in rows:
        r_words = r["task_name"].lower().split()
        if any(w in r_words for w in words):
            delete_reminder(r["id"])
            return r

    # 3. Generic "alarm" request (cancels nearest if only 1 exists)
    if len(rows) == 1 or clean in ["alarm", "all alarms", "the alarm", ""]:
        delete_reminder(rows[0]["id"])
        return rows[0]

    return None

if __name__ == "__main__":
    init_db()
    test_id = insert_reminder("Study AWS Solutions Architect", "2026-09-22T15:00:00Z")
    print(f"Inserted test reminder with ID: {test_id}")
    print("Current Reminders in DB:", get_all_reminders())