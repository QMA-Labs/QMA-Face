import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


class ChatStore:
    def __init__(self, root: Path, *, memory: bool = False):
        self.root = root.resolve()
        self.memory = memory
        self._memory_connection = None
        if not memory:
            self.root.mkdir(parents=True, exist_ok=True)
        self.database = ":memory:" if memory else self.root / "qma-face.sqlite3"
        self.attachments = self.root / "attachments"
        if not memory:
            self.attachments.mkdir(exist_ok=True)
        with self.connection() as connection:
            if connection.execute("PRAGMA user_version").fetchone()[0] > 1:
                raise ValueError("Database schema is newer than this application")
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS chats (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, language TEXT NOT NULL
                    CHECK(language IN ('en','fr')), created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL, photo_name TEXT,
                    photo_kept INTEGER NOT NULL DEFAULT 0 CHECK(photo_kept IN (0,1))
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user','assistant')), content TEXT NOT NULL,
                    created_at TEXT NOT NULL, metadata TEXT NOT NULL DEFAULT '{}',
                    FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS messages_by_chat ON messages(chat_id,id);
                PRAGMA user_version=1;
            """)

    @contextmanager
    def connection(self):
        if self.memory:
            if self._memory_connection is None:
                self._memory_connection = sqlite3.connect(":memory:", timeout=10)
            connection = self._memory_connection
        else:
            connection = sqlite3.connect(self.database, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA secure_delete=ON")
        try:
            with connection:
                yield connection
        finally:
            if not self.memory:
                connection.close()

    def setting(self, key: str, default: str = "") -> str:
        with self.connection() as connection:
            row = connection.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO settings VALUES (?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    def create_chat(self, language: str, title: str) -> str:
        if language not in {"en", "fr"}:
            raise ValueError("Unsupported language")
        identity = uuid4().hex
        stamp = now()
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO chats(id,title,language,created_at,updated_at) VALUES (?,?,?,?,?)",
                (identity, title, language, stamp, stamp),
            )
        self.set_setting("last_chat_id", identity)
        return identity

    def get_chat(self, identity: str | None) -> dict | None:
        if not identity:
            return None
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM chats WHERE id=?", (identity,)).fetchone()
        return dict(row) if row else None

    def list_chats(self) -> list[dict]:
        with self.connection() as connection:
            rows = connection.execute("SELECT * FROM chats ORDER BY updated_at DESC,id").fetchall()
        return [dict(row) for row in rows]

    def set_language(self, identity: str, language: str) -> None:
        if language not in {"en", "fr"}:
            raise ValueError("Unsupported language")
        with self.connection() as connection:
            connection.execute("UPDATE chats SET language=? WHERE id=?", (language, identity))

    def add_message(
        self, identity: str, role: str, content: str, metadata: dict | None = None
    ) -> int:
        if role not in {"user", "assistant"} or not content.strip():
            raise ValueError("Invalid chat message")
        stamp = now()
        with self.connection() as connection:
            cursor = connection.execute(
                "INSERT INTO messages(chat_id,role,content,created_at,metadata) VALUES (?,?,?,?,?)",
                (identity, role, content, stamp, json.dumps(metadata or {})),
            )
            connection.execute("UPDATE chats SET updated_at=? WHERE id=?", (stamp, identity))
            if role == "user":
                count = connection.execute(
                    "SELECT COUNT(*) FROM messages WHERE chat_id=? AND role='user'", (identity,)
                ).fetchone()[0]
                if count == 1:
                    title = " ".join(content.split())[:64]
                    connection.execute("UPDATE chats SET title=? WHERE id=?", (title, identity))
        return int(cursor.lastrowid)

    def messages(self, identity: str) -> list[dict]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM messages WHERE chat_id=? ORDER BY id", (identity,)
            ).fetchall()
        result = []
        for row in rows:
            value = dict(row)
            value["metadata"] = json.loads(value["metadata"])
            result.append(value)
        return result

    def attachment_path(self, identity: str) -> Path:
        if self.memory:
            raise ValueError("Temporary sessions cannot save attachments")
        if len(identity) != 32 or any(c not in "0123456789abcdef" for c in identity):
            raise ValueError("Invalid attachment identity")
        return self.attachments / f"{identity}.png"

    def set_photo(self, identity: str, filename: str | None, kept: bool) -> None:
        with self.connection() as connection:
            connection.execute(
                "UPDATE chats SET photo_name=?,photo_kept=?,updated_at=? WHERE id=?",
                (Path(filename).name if filename else None, int(kept), now(), identity),
            )

    def delete_chat(self, identity: str) -> None:
        path = None if self.memory else self.attachment_path(identity)
        with self.connection() as connection:
            connection.execute("DELETE FROM chats WHERE id=?", (identity,))
            connection.execute(
                "DELETE FROM settings WHERE key='last_chat_id' AND value=?", (identity,)
            )
        if path:
            path.unlink(missing_ok=True)

    def delete_analysis(self, identity: str) -> None:
        """Remove measurements AND any reply that may paraphrase them, keeping user text."""
        with self.connection() as connection:
            connection.execute(
                "DELETE FROM messages WHERE chat_id=? AND role='assistant'", (identity,)
            )

    def delete_all_chats(self) -> None:
        for chat in self.list_chats():
            self.delete_chat(chat["id"])

    def close(self) -> None:
        if self._memory_connection is not None:
            self._memory_connection.close()
            self._memory_connection = None
