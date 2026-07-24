#!/usr/bin/env python
"""
Local durable history for the Growatt gateway.

growatt_gateway.py only ever caches the single most recent reading in
memory -- restart the process and it's gone, and there was never any local
record of solar history independent of whatever main-pi5's Prometheus
happened to successfully scrape. Since Prometheus is pull-based, a network
blip between this Pi and main-pi5 during a scrape is a permanent gap in its
timeline; there's no retry or backfill on that side. This module gives the
gateway its own durable SQLite log of every real reading, written locally
regardless of whether anything downstream is currently reachable, so that
window is never actually lost -- see docs/GATEWAY.md "Local history buffer".

Columns match scale_reading()'s keys 1:1 (see growatt_common.py) so a row
can be cross-referenced against a Prometheus homelab_solar_* sample by name.
"""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

READING_FIELDS = [
    'status', 'vpv1_v', 'vpv2_v', 'ppv1_w', 'ppv2_w', 'output_w', 'output_va',
    'bat_volt_v', 'bat_soc_pct', 'bat_watt_w', 'bus_volt_v', 'grid_volt_v',
    'grid_freq_hz', 'output_volt_v', 'output_freq_hz', 'load_percent',
    'inv_temp_c', 'dcdc_temp_c',
]


def _cutoff_iso(hours):
    """Python-computed, T-separated cutoff -- deliberately NOT SQLite's own
    datetime('now', '-N hours'), which is space-separated and offset-less.
    Comparing that against T-separated stored timestamps as text silently
    degrades to a date-only check (a real bug hit and fixed the same day in
    monitor-cam-webapp's history queries -- see that repo's git history)."""
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


@contextmanager
def _connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path):
    columns = ', '.join(f'{f} REAL' for f in READING_FIELDS)
    with _connect(db_path) as conn:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS readings (
                timestamp TEXT PRIMARY KEY,
                {columns}
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_readings_timestamp ON readings(timestamp)")


def log_reading(db_path, timestamp_iso, reading):
    """Insert one reading. `reading` is scale_reading()'s output -- only
    real, fresh (source='modbus', not stale) readings should ever reach
    here; the gateway enforces that before calling this."""
    columns = ['timestamp'] + READING_FIELDS
    placeholders = ', '.join('?' for _ in columns)
    values = [timestamp_iso] + [reading.get(f) for f in READING_FIELDS]
    with _connect(db_path) as conn:
        conn.execute(
            f"INSERT OR REPLACE INTO readings ({', '.join(columns)}) VALUES ({placeholders})",
            values,
        )


def get_history(db_path, hours=24, limit=10000):
    with _connect(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM readings WHERE timestamp >= ? ORDER BY timestamp ASC LIMIT ?""",
            (_cutoff_iso(hours), limit),
        ).fetchall()
        return [dict(r) for r in rows]


def prune_old(db_path, keep_days=180):
    """Delete rows older than keep_days. Cheap enough to call frequently;
    the gateway only calls this once a day (see growatt_gateway.py)."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=keep_days)).isoformat()
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM readings WHERE timestamp < ?", (cutoff,))
