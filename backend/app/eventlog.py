"""SQLite event log. Stores decisions and Guard request ids, never message text."""
from __future__ import annotations

import sqlite3
import threading
import time


class EventLog:
    def __init__(self, path: str):
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS events ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, session_id TEXT, mode TEXT, "
                "stage TEXT, decision TEXT, fired_layer TEXT, guard_request_id TEXT, latency_ms REAL)"
            )
            self._db.commit()

    def record(self, *, session_id: str, mode: str, stage: str, decision: str,
               fired_layer: str | None = None, guard_request_id: str | None = None,
               latency_ms: float = 0.0) -> None:
        with self._lock:
            self._db.execute(
                "INSERT INTO events (ts, session_id, mode, stage, decision, fired_layer, "
                "guard_request_id, latency_ms) VALUES (?,?,?,?,?,?,?,?)",
                (time.time(), session_id, mode, stage, decision, fired_layer,
                 guard_request_id, latency_ms),
            )
            self._db.commit()

    def count(self) -> int:
        with self._lock:
            return self._db.execute("SELECT COUNT(*) FROM events").fetchone()[0]

    def close(self) -> None:
        self._db.close()
