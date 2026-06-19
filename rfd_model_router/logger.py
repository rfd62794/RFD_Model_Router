import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "requests.db"


def init_db() -> None:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    input_tokens INTEGER,
                    output_tokens INTEGER,
                    duration_ms INTEGER,
                    success INTEGER NOT NULL
                )
                """
            )
            conn.commit()
    except Exception:
        pass


def log_request(
    task_type: str,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    duration_ms: int,
    success: bool,
) -> None:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO requests
                (timestamp, task_type, provider, model, input_tokens, output_tokens, duration_ms, success)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    task_type,
                    provider,
                    model,
                    input_tokens,
                    output_tokens,
                    duration_ms,
                    int(success),
                ),
            )
            conn.commit()
    except Exception:
        pass
