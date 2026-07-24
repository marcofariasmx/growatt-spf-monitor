"""Tests for growatt_storage.py: the local durable SQLite history that lets
the gateway survive restarts and Prometheus scrape gaps without losing
readings (see docs/GATEWAY.md 'Local history buffer')."""
from datetime import datetime, timedelta, timezone

import growatt_storage as storage

_SAMPLE_READING = {
    'status': 12, 'vpv1_v': 76.4, 'vpv2_v': 0.0, 'ppv1_w': 96.0, 'ppv2_w': 0.0,
    'output_w': 74.0, 'output_va': 121.0, 'bat_volt_v': 53.51, 'bat_soc_pct': 96,
    'bat_watt_w': -16.0, 'bus_volt_v': 55.0, 'grid_volt_v': 0.0, 'grid_freq_hz': 0.0,
    'output_volt_v': 120.0, 'output_freq_hz': 60.0, 'load_percent': 4,
    'inv_temp_c': 25.0, 'dcdc_temp_c': 24.0,
}


def _iso(hours_ago=0):
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()


def test_init_db_is_idempotent(tmp_path):
    db_path = str(tmp_path / "solar.db")
    storage.init_db(db_path)
    storage.init_db(db_path)  # must not raise on a pre-existing table


def test_log_and_retrieve_a_reading(tmp_path):
    db_path = str(tmp_path / "solar.db")
    storage.init_db(db_path)

    ts = _iso()
    storage.log_reading(db_path, ts, _SAMPLE_READING)

    rows = storage.get_history(db_path, hours=1)
    assert len(rows) == 1
    assert rows[0]['timestamp'] == ts
    assert rows[0]['bat_soc_pct'] == 96
    assert rows[0]['bat_watt_w'] == -16.0


def test_get_history_excludes_readings_outside_the_window(tmp_path):
    db_path = str(tmp_path / "solar.db")
    storage.init_db(db_path)

    storage.log_reading(db_path, _iso(hours_ago=48), _SAMPLE_READING)
    storage.log_reading(db_path, _iso(hours_ago=1), _SAMPLE_READING)

    rows = storage.get_history(db_path, hours=24)
    assert len(rows) == 1


def test_get_history_orders_oldest_first(tmp_path):
    db_path = str(tmp_path / "solar.db")
    storage.init_db(db_path)

    storage.log_reading(db_path, _iso(hours_ago=2), {**_SAMPLE_READING, 'bat_soc_pct': 80})
    storage.log_reading(db_path, _iso(hours_ago=1), {**_SAMPLE_READING, 'bat_soc_pct': 90})

    rows = storage.get_history(db_path, hours=24)
    assert [r['bat_soc_pct'] for r in rows] == [80, 90]


def test_prune_old_removes_rows_past_retention(tmp_path):
    db_path = str(tmp_path / "solar.db")
    storage.init_db(db_path)

    storage.log_reading(db_path, _iso(hours_ago=24 * 200), _SAMPLE_READING)  # 200 days old
    storage.log_reading(db_path, _iso(hours_ago=1), _SAMPLE_READING)

    storage.prune_old(db_path, keep_days=180)

    rows = storage.get_history(db_path, hours=24 * 365)
    assert len(rows) == 1


def test_log_reading_upserts_same_timestamp(tmp_path):
    """INSERT OR REPLACE: a re-logged reading at the same timestamp (e.g. a
    retry) overwrites rather than duplicating."""
    db_path = str(tmp_path / "solar.db")
    storage.init_db(db_path)

    ts = _iso()
    storage.log_reading(db_path, ts, {**_SAMPLE_READING, 'bat_soc_pct': 50})
    storage.log_reading(db_path, ts, {**_SAMPLE_READING, 'bat_soc_pct': 51})

    rows = storage.get_history(db_path, hours=1)
    assert len(rows) == 1
    assert rows[0]['bat_soc_pct'] == 51
