# -*- coding: utf-8 -*-
"""Lightweight SQLite history manager for Just Translate with automatic capacity pruning."""

import sqlite3
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from contextlib import contextmanager
from config.settings import settings

class HistoryManager:
    """Manages translation and output history using an embedded, ultra-lightweight SQLite database."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            data_dir = settings.file_path.parent / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = data_dir / "history.db"
        else:
            self.db_path = db_path
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    source_lang TEXT,
                    target_lang TEXT,
                    model TEXT,
                    input_text TEXT NOT NULL,
                    output_text TEXT NOT NULL,
                    ttft_ms REAL DEFAULT 0.0,
                    speed_tok_s REAL DEFAULT 0.0,
                    duration_s REAL DEFAULT 0.0
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_history_created ON history (created_at DESC);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_history_mode ON history (mode);")
            conn.commit()

    def add_record(
        self,
        mode: str,
        source_lang: str,
        target_lang: str,
        model: str,
        input_text: str,
        output_text: str,
        ttft_ms: float = 0.0,
        speed_tok_s: float = 0.0,
        duration_s: float = 0.0
    ) -> int:
        """Inserts a new record and automatically prunes oldest records exceeding history_limit."""
        if not input_text.strip() or not output_text.strip():
            return -1

        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        limit = int(settings.get("history_limit", 100))

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO history (
                    created_at, mode, source_lang, target_lang, model, 
                    input_text, output_text, ttft_ms, speed_tok_s, duration_s
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                now_str, mode, source_lang, target_lang, model,
                input_text.strip(), output_text.strip(),
                round(ttft_ms, 1), round(speed_tok_s, 1), round(duration_s, 2)
            ))
            new_id = cursor.lastrowid

            # 自动保留最近 limit 条，修剪多余历史
            cursor.execute("""
                DELETE FROM history WHERE id NOT IN (
                    SELECT id FROM history ORDER BY id DESC LIMIT ?
                )
            """, (limit,))
            conn.commit()
            return new_id

    def get_records(
        self,
        mode: Optional[str] = None,
        keyword: Optional[str] = None,
        limit: int = 500
    ) -> List[Dict[str, Any]]:
        """Retrieves history records filtered by mode and/or search keyword."""
        query = "SELECT * FROM history WHERE 1=1"
        params = []

        if mode and mode != "all":
            query += " AND mode = ?"
            params.append(mode)

        if keyword and keyword.strip():
            kw = f"%{keyword.strip()}%"
            query += " AND (input_text LIKE ? OR output_text LIKE ? OR model LIKE ?)"
            params.extend([kw, kw, kw])

        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def delete_record(self, record_id: int) -> bool:
        """Deletes a single history record by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM history WHERE id = ?", (record_id,))
            conn.commit()
            return cursor.rowcount > 0

    def clear_all(self):
        """Clears all history records."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM history;")
            conn.commit()

    def get_count(self) -> int:
        """Returns the total number of history records currently stored."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM history")
            return cursor.fetchone()[0]


# 全局单例
history_manager = HistoryManager()
