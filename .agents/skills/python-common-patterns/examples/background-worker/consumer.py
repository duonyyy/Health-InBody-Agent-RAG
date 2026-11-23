"""Minimal atomic inbox + effect demo using the Python standard library.

This demonstrates a local database pattern only, NOT a production message consumer.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class Message:
    event_id: str
    order_id: str


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS inbox (
            event_id TEXT PRIMARY KEY
        );
        CREATE TABLE IF NOT EXISTS processed_orders (
            order_id TEXT PRIMARY KEY,
            event_id TEXT NOT NULL UNIQUE
        );
        """
    )
    conn.commit()


def consume(conn: sqlite3.Connection, message: Message) -> bool:
    """Returns True for new effect, False if duplicate event.

    SQLite BEGIN IMMEDIATE serializes concurrent writers; PostgreSQL would use
    its own SQL upsert/transaction semantics. The caller ACKs only after True/False
    returns successfully (after the DB transaction commits).
    """
    if not message.event_id or not message.order_id:
        raise ValueError("event_id and order_id must be non-empty")
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "INSERT INTO inbox(event_id) VALUES (?) ON CONFLICT(event_id) DO NOTHING",
            (message.event_id,),
        )
        if row.rowcount == 0:
            conn.commit()
            return False  # duplicate — no effect
        conn.execute(
            "INSERT INTO processed_orders(order_id, event_id) VALUES (?, ?)",
            (message.order_id, message.event_id),
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise


if __name__ == "__main__":
    db = sqlite3.connect(":memory:")
    try:
        init_db(db)
        event = Message("event-001", "order-001")
        print("first delivery:", consume(db, event))
        print("redelivery:", consume(db, event))
    finally:
        db.close()
