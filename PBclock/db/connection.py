"""SQLite 连接管理 (单例)"""

import sqlite3
import os
from threading import Lock


DB_DIR = os.path.join(os.path.expanduser("~"), "AppData", "Local", "PBclock")
DB_PATH = os.path.join(DB_DIR, "pbclock.db")


class Database:
    """SQLite 数据库单例"""
    _instance: "Database | None" = None
    _lock = Lock()

    def __new__(cls) -> "Database":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        os.makedirs(DB_DIR, exist_ok=True)
        self._conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._initialized = True

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    def execute(self, sql: str, params: tuple = ()):
        return self._conn.execute(sql, params)

    def commit(self):
        self._conn.commit()

    def close(self):
        if self._conn:
            self._conn.close()
            Database._instance = None
            self._initialized = False
