import sqlite3
from typing import Any

from flask import current_app

SCHEMA = """
CREATE TABLE IF NOT EXISTS medicines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    strength TEXT NOT NULL DEFAULT '',
    company TEXT,
    strips_per_box INTEGER NOT NULL DEFAULT 1,
    UNIQUE (name, strength)
);

CREATE TABLE IF NOT EXISTS batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    medicine_id INTEGER NOT NULL REFERENCES medicines(id),
    distributor TEXT,
    invoice_no TEXT,
    batch_no TEXT NOT NULL,
    expiry TEXT NOT NULL,
    strips INTEGER NOT NULL,
    cost_box REAL NOT NULL,
    sale_box REAL NOT NULL,
    received_on TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created TEXT NOT NULL,
    customer TEXT NOT NULL DEFAULT '',
    total REAL NOT NULL,
    profit REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS sale_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL REFERENCES sales(id),
    medicine_id INTEGER NOT NULL REFERENCES medicines(id),
    batch_id INTEGER NOT NULL REFERENCES batches(id),
    mode TEXT NOT NULL,
    strips INTEGER NOT NULL,
    price_strip REAL NOT NULL,
    cost_strip REAL NOT NULL
);
"""


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(current_app.config["DATABASE"])
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_db()
    conn.executescript(SCHEMA)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(sales)")]
    if "customer" not in cols:
        conn.execute("ALTER TABLE sales ADD COLUMN customer TEXT NOT NULL DEFAULT ''")
    conn.commit()
    conn.close()


def rows_as_dicts(rows: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]
