import asyncio
import json
import sqlite3
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from backend.config import DB_PATH


class AsyncDBPool:
    def __init__(self, pool_size: int = 5):
        self._pool: asyncio.Queue[sqlite3.Connection] = asyncio.Queue(maxsize=pool_size)
        self._size = pool_size

    async def start(self):
        for _ in range(self._size):
            conn = await asyncio.to_thread(self._create_conn)
            await self._pool.put(conn)

    async def stop(self):
        for _ in range(self._size):
            try:
                conn = await asyncio.wait_for(self._pool.get(), timeout=2.0)
                conn.close()
            except (asyncio.TimeoutError, Exception):
                break

    @staticmethod
    def _create_conn() -> sqlite3.Connection:
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA cache_size=-8000")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @asynccontextmanager
    async def connect(self):
        conn = await self._pool.get()
        try:
            yield conn
        finally:
            await self._pool.put(conn)


db_pool = AsyncDBPool()


async def init_db():
    async with db_pool.connect() as conn:
        def _init(c):
            c.execute("""
                CREATE TABLE IF NOT EXISTS cases (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL DEFAULT 'PENDING',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    destination_country TEXT,
                    destination_city TEXT,
                    hire_profile TEXT,
                    document_data TEXT,
                    compliance_result TEXT,
                    relocation_guide TEXT,
                    error TEXT,
                    current_stage TEXT DEFAULT 'intake',
                    case_type TEXT DEFAULT 'relocation'
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'PENDING',
                    document_type TEXT,
                    confidence_score INTEGER,
                    confidence_label TEXT,
                    extracted_data TEXT,
                    date_errors TEXT DEFAULT '[]',
                    date_warnings TEXT DEFAULT '[]',
                    error TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (case_id) REFERENCES cases(id)
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS stage_transitions (
                    id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    entered_at TEXT NOT NULL,
                    actor TEXT NOT NULL DEFAULT 'system',
                    decision TEXT,
                    details TEXT,
                    FOREIGN KEY (case_id) REFERENCES cases(id)
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_documents_case ON documents(case_id)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_transitions_case ON stage_transitions(case_id)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_cases_created ON cases(created_at DESC)")
            c.commit()
        await asyncio.to_thread(_init, conn)


async def get_case_async(case_id: str) -> dict | None:
    async with db_pool.connect() as conn:
        def _get(c):
            row = c.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
            if row is None:
                return None
            d = dict(row)
            for field in ["hire_profile", "document_data", "compliance_result"]:
                if d.get(field) and isinstance(d[field], str):
                    try:
                        d[field] = json.loads(d[field])
                    except (json.JSONDecodeError, TypeError):
                        pass
            return d
        return await asyncio.to_thread(_get, conn)


async def update_case_async(case_id: str, **kwargs):
    now = datetime.now(timezone.utc).isoformat()
    kwargs["updated_at"] = now
    async with db_pool.connect() as conn:
        def _update(c):
            sets = ", ".join(f"{k} = ?" for k in kwargs)
            vals = list(kwargs.values()) + [case_id]
            c.execute(f"UPDATE cases SET {sets} WHERE id = ?", vals)
            c.commit()
        await asyncio.to_thread(_update, conn)


async def insert_case_async(**kwargs):
    async with db_pool.connect() as conn:
        def _insert(c):
            fields = ", ".join(kwargs.keys())
            placeholders = ", ".join("?" for _ in kwargs)
            c.execute(f"INSERT INTO cases ({fields}) VALUES ({placeholders})", list(kwargs.values()))
            c.commit()
        await asyncio.to_thread(_insert, conn)


async def list_cases_async() -> list:
    async with db_pool.connect() as conn:
        def _list(c):
            rows = c.execute(
                "SELECT id, status, created_at, updated_at, destination_country, destination_city FROM cases ORDER BY created_at DESC"
            ).fetchall()
            return [dict(r) for r in rows]
        return await asyncio.to_thread(_list, conn)


async def insert_document_async(**kwargs):
    async with db_pool.connect() as conn:
        def _insert(c):
            fields = ", ".join(kwargs.keys())
            placeholders = ", ".join("?" for _ in kwargs)
            c.execute(f"INSERT INTO documents ({fields}) VALUES ({placeholders})", list(kwargs.values()))
            c.commit()
        await asyncio.to_thread(_insert, conn)


async def update_document_async(doc_id: str, **kwargs):
    async with db_pool.connect() as conn:
        def _update(c):
            sets = ", ".join(f"{k} = ?" for k in kwargs)
            vals = list(kwargs.values()) + [doc_id]
            c.execute(f"UPDATE documents SET {sets} WHERE id = ?", vals)
            c.commit()
        await asyncio.to_thread(_update, conn)


async def get_case_documents_async(case_id: str) -> list[dict]:
    async with db_pool.connect() as conn:
        def _get(c):
            rows = c.execute(
                "SELECT * FROM documents WHERE case_id = ? ORDER BY created_at", (case_id,)
            ).fetchall()
            result = []
            for r in rows:
                d = dict(r)
                for field in ["extracted_data"]:
                    if d.get(field) and isinstance(d[field], str):
                        try:
                            d[field] = json.loads(d[field])
                        except (json.JSONDecodeError, TypeError):
                            pass
                for field in ["date_errors", "date_warnings"]:
                    if d.get(field) and isinstance(d[field], str):
                        try:
                            d[field] = json.loads(d[field])
                        except (json.JSONDecodeError, TypeError):
                            d[field] = []
            return result
        return await asyncio.to_thread(_get, conn)


async def record_stage(case_id: str, stage: str, actor: str = "system", details: str = None, decision: str = None):
    sid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    async with db_pool.connect() as conn:
        def _insert(c):
            c.execute(
                "INSERT INTO stage_transitions (id, case_id, stage, entered_at, actor, decision, details) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (sid, case_id, stage, now, actor, decision, details)
            )
            c.commit()
        await asyncio.to_thread(_insert, conn)


async def get_case_stages_async(case_id: str) -> list[dict]:
    async with db_pool.connect() as conn:
        def _get(c):
            rows = c.execute(
                "SELECT * FROM stage_transitions WHERE case_id = ? ORDER BY entered_at", (case_id,)
            ).fetchall()
            return [dict(r) for r in rows]
        return await asyncio.to_thread(_get, conn)
