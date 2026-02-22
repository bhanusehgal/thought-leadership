from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .states import StateError, can_transition


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AgentDB:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @contextmanager
    def tx(self) -> Iterable[sqlite3.Connection]:
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS articles (
                    id TEXT PRIMARY KEY,
                    pillar TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    week_type TEXT NOT NULL,
                    state TEXT NOT NULL,
                    title TEXT,
                    subtitle TEXT,
                    tldr TEXT,
                    body_markdown TEXT,
                    tags_json TEXT NOT NULL DEFAULT '[]',
                    title_options_json TEXT NOT NULL DEFAULT '[]',
                    image_suggestions_json TEXT NOT NULL DEFAULT '[]',
                    citations_json TEXT NOT NULL DEFAULT '[]',
                    claims_verification_json TEXT NOT NULL DEFAULT '[]',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    scheduled_publish_at TEXT,
                    published_url TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS state_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article_id TEXT NOT NULL,
                    from_state TEXT NOT NULL,
                    to_state TEXT NOT NULL,
                    reason TEXT,
                    at TEXT NOT NULL,
                    FOREIGN KEY(article_id) REFERENCES articles(id)
                );

                CREATE INDEX IF NOT EXISTS idx_articles_state ON articles(state);
                """
            )

    def insert_article(self, data: dict[str, Any]) -> None:
        now = utc_now()
        payload = {
            "id": data["id"],
            "pillar": data["pillar"],
            "topic": data["topic"],
            "week_type": data["week_type"],
            "state": data.get("state", "IDEA"),
            "title": data.get("title"),
            "subtitle": data.get("subtitle"),
            "tldr": data.get("tldr"),
            "body_markdown": data.get("body_markdown"),
            "tags_json": json.dumps(data.get("tags", [])),
            "title_options_json": json.dumps(data.get("title_options", [])),
            "image_suggestions_json": json.dumps(data.get("image_suggestions", [])),
            "citations_json": json.dumps(data.get("citations", [])),
            "claims_verification_json": json.dumps(data.get("claims_verification", [])),
            "metadata_json": json.dumps(data.get("metadata", {})),
            "scheduled_publish_at": data.get("scheduled_publish_at"),
            "published_url": data.get("published_url"),
            "created_at": now,
            "updated_at": now,
        }
        with self.tx() as conn:
            conn.execute(
                """
                INSERT INTO articles (
                    id, pillar, topic, week_type, state, title, subtitle, tldr, body_markdown,
                    tags_json, title_options_json, image_suggestions_json, citations_json,
                    claims_verification_json, metadata_json, scheduled_publish_at,
                    published_url, created_at, updated_at
                )
                VALUES (
                    :id, :pillar, :topic, :week_type, :state, :title, :subtitle, :tldr, :body_markdown,
                    :tags_json, :title_options_json, :image_suggestions_json, :citations_json,
                    :claims_verification_json, :metadata_json, :scheduled_publish_at,
                    :published_url, :created_at, :updated_at
                )
                """,
                payload,
            )

    def update_article(self, article_id: str, **fields: Any) -> None:
        if not fields:
            return
        cols = []
        values: dict[str, Any] = {"id": article_id}
        for key, value in fields.items():
            db_key = key
            if key in {
                "tags",
                "title_options",
                "image_suggestions",
                "citations",
                "claims_verification",
                "metadata",
            }:
                db_key = f"{key}_json"
                value = json.dumps(value)
            cols.append(f"{db_key}=:{db_key}")
            values[db_key] = value
        cols.append("updated_at=:updated_at")
        values["updated_at"] = utc_now()
        sql = f"UPDATE articles SET {', '.join(cols)} WHERE id=:id"
        with self.tx() as conn:
            conn.execute(sql, values)

    def get_article(self, article_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM articles WHERE id=?", (article_id,)).fetchone()
        if not row:
            raise KeyError(f"Article not found: {article_id}")
        return self._row_to_dict(row)

    def list_articles(self, state: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM articles"
        params: tuple[Any, ...] = ()
        if state:
            query += " WHERE state=?"
            params = (state,)
        query += " ORDER BY created_at DESC"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def count_state(self, state: str) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM articles WHERE state=?", (state,)).fetchone()
        return int(row["c"])

    def transition(self, article_id: str, to_state: str, reason: str | None = None) -> None:
        with self.tx() as conn:
            row = conn.execute("SELECT state FROM articles WHERE id=?", (article_id,)).fetchone()
            if not row:
                raise KeyError(f"Article not found: {article_id}")
            from_state = row["state"]
            if not can_transition(from_state, to_state):
                raise StateError(f"Illegal transition {from_state} -> {to_state}")
            if to_state == "READY_FOR_REVIEW":
                ready_count = conn.execute(
                    "SELECT COUNT(*) AS c FROM articles WHERE state='READY_FOR_REVIEW' AND id != ?",
                    (article_id,),
                ).fetchone()["c"]
                if int(ready_count) >= 3:
                    raise StateError("READY_FOR_REVIEW queue is full (max 3).")

            now = utc_now()
            conn.execute(
                "UPDATE articles SET state=?, updated_at=? WHERE id=?",
                (to_state, now, article_id),
            )
            conn.execute(
                """
                INSERT INTO state_history (article_id, from_state, to_state, reason, at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (article_id, from_state, to_state, reason or "", now),
            )

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        d["tags"] = json.loads(d.pop("tags_json"))
        d["title_options"] = json.loads(d.pop("title_options_json"))
        d["image_suggestions"] = json.loads(d.pop("image_suggestions_json"))
        d["citations"] = json.loads(d.pop("citations_json"))
        d["claims_verification"] = json.loads(d.pop("claims_verification_json"))
        d["metadata"] = json.loads(d.pop("metadata_json"))
        return d
