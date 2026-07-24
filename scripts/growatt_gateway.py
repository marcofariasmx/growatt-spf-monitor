#!/usr/bin/env python
"""
Growatt Local Gateway

The single owner of the Modbus RTU connection to the SPF inverter. Polls
the inverter on a fixed interval and caches the latest reading in memory,
exposed over a local-only HTTP API:

  GET /latest  -> most recent reading (raw registers + scaled values +
                  timestamp + source + staleness flag)
  GET /health  -> gateway/Modbus connection status

Other processes on the same host (growatt_cloud.py, local dashboards,
logging, etc.) should read from this API instead of opening the serial
port themselves -- pyserial takes an exclusive lock on the port, so two
processes polling the inverter at once simply fails (see docs/GATEWAY.md
for how this was discovered).

If the inverter can't be reached at all (no port, hardware fault), the
gateway falls back to test_data/inverter_snapshot.json so downstream
tooling still has something to develop against -- but every response
says so via "source": "test_data", rather than pretending to be live.

Self-healing: a total read failure (every register in one read_all()
cycle failing, not just a couple) triggers a soft reconnect after
GATEWAY_RECONNECT_AFTER_FAILURES consecutive cycles, and the poll loop
also keeps trying to establish the initial connection if the adapter
wasn't present at startup. This recovers from most transient faults on
its own; growatt_watchdog.py handles the harder case (a wedged USB
endpoint that only a reboot clears -- see docs/GATEWAY.md).
"""

import os
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.responses import JSONResponse

import growatt_storage as storage
from growatt_common import InverterReader, load_env, load_test_data, scale_reading

ENV = load_env()

MODBUS_PORT = ENV.get('MODBUS_PORT', '/dev/ttyUSB0')
MODBUS_BAUDRATE = int(ENV.get('MODBUS_BAUDRATE', '9600'))
MODBUS_DEVICE_ID = int(ENV.get('MODBUS_DEVICE_ID', '1'))

GATEWAY_HOST = ENV.get('GATEWAY_HOST', '127.0.0.1')
GATEWAY_PORT = int(ENV.get('GATEWAY_PORT', '8090'))
POLL_INTERVAL = float(ENV.get('GATEWAY_POLL_INTERVAL', '15'))
STALE_AFTER = float(ENV.get('GATEWAY_STALE_AFTER', '90'))
RECONNECT_AFTER_FAILURES = int(ENV.get('GATEWAY_RECONNECT_AFTER_FAILURES', '3'))

# Local durable history (see growatt_storage.py / docs/GATEWAY.md). Decoupled
# from POLL_INTERVAL on purpose -- logging every 15s would be ~5700 SD-card
# writes/day for no real benefit; this fleet has SD-corruption history.
LOG_DB_PATH = ENV.get('GATEWAY_LOG_DB', os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'solar_history.db'
))
LOG_INTERVAL = float(ENV.get('GATEWAY_LOG_INTERVAL', '60'))
LOG_RETENTION_DAYS = int(ENV.get('GATEWAY_LOG_RETENTION_DAYS', '180'))


class GatewayState:
    """Thread-safe holder for the most recent reading."""

    def __init__(self):
        self._lock = threading.Lock()
        self._raw = None
        self._scaled = None
        self._timestamp = None
        self._source = 'none'

    def update(self, raw, source):
        with self._lock:
            self._raw = raw
            self._scaled = scale_reading(raw)
            self._timestamp = datetime.now(timezone.utc)
            self._source = source

    def snapshot(self):
        with self._lock:
            if self._timestamp is None:
                return None
            age = (datetime.now(timezone.utc) - self._timestamp).total_seconds()
            return {
                'raw_registers': self._raw,
                'reading': self._scaled,
                'timestamp': self._timestamp.isoformat(),
                'age_seconds': round(age, 1),
                'stale': age > STALE_AFTER,
                'source': self._source,
            }


state = GatewayState()
_inverter = None
_test_data = None
_stop_event = threading.Event()
_poll_thread = None
_consecutive_total_failures = 0
_last_log_time = 0.0
_last_prune_time = 0.0


def _try_late_connect():
    """If the adapter wasn't present (or connect() failed) at startup,
    keep checking for it -- lets the gateway self-heal from a replug or a
    transient boot-time race without needing a service restart."""
    global _inverter
    if _inverter is not None or not os.path.exists(MODBUS_PORT):
        return
    candidate = InverterReader(MODBUS_PORT, MODBUS_BAUDRATE, MODBUS_DEVICE_ID)
    if candidate.connect():
        print(f"[{datetime.now()}] Gateway: inverter became available, connected")
        _inverter = candidate


def _maybe_log_reading(source):
    """Append the just-updated state to the local durable history, throttled
    to LOG_INTERVAL and gated to real readings only -- never test_data, same
    discipline as growatt_cloud.py's should_upload(). Also prunes once a day."""
    global _last_log_time, _last_prune_time

    now = time.monotonic()
    if source == 'modbus' and now - _last_log_time >= LOG_INTERVAL:
        snap = state.snapshot()
        if snap is not None:
            try:
                storage.log_reading(LOG_DB_PATH, snap['timestamp'], snap['reading'])
                _last_log_time = now
            except Exception as e:
                print(f"[{datetime.now()}] Gateway: failed to log reading locally: {e}")

    if now - _last_prune_time >= 86400:
        try:
            storage.prune_old(LOG_DB_PATH, keep_days=LOG_RETENTION_DAYS)
            _last_prune_time = now
        except Exception as e:
            print(f"[{datetime.now()}] Gateway: failed to prune local history: {e}")


def _poll_loop():
    global _consecutive_total_failures

    while not _stop_event.is_set():
        raw = None
        source = None

        _try_late_connect()

        if _inverter is not None:
            try:
                candidate = _inverter.read_all()
                if _inverter.all_reads_failed:
                    _consecutive_total_failures += 1
                    print(f"[{datetime.now()}] Gateway: every register read failed this "
                          f"cycle ({_consecutive_total_failures} consecutive) -- "
                          f"treating as no reading, not as a live zero")
                else:
                    _consecutive_total_failures = 0
                    raw = candidate
                    source = 'modbus'
            except Exception as e:
                _consecutive_total_failures += 1
                print(f"[{datetime.now()}] Gateway poll error: {e}")

            if _consecutive_total_failures >= RECONNECT_AFTER_FAILURES:
                print(f"[{datetime.now()}] Gateway: {_consecutive_total_failures} consecutive "
                      f"failed cycles, attempting a soft reconnect")
                _inverter.disconnect()
                if _inverter.connect():
                    print(f"[{datetime.now()}] Gateway: reconnected successfully")
                else:
                    print(f"[{datetime.now()}] Gateway: reconnect attempt failed, will keep retrying")
                _consecutive_total_failures = 0

        if raw is None and _test_data is not None:
            raw = _test_data
            source = 'test_data'

        if raw is not None:
            state.update(raw, source)
            _maybe_log_reading(source)

        _stop_event.wait(POLL_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _inverter, _test_data, _poll_thread

    print("=" * 60)
    print("Growatt Local Gateway")
    print("=" * 60)
    print(f"Modbus:  {MODBUS_PORT} @ {MODBUS_BAUDRATE} baud (device_id={MODBUS_DEVICE_ID})")
    print(f"Listen:  {GATEWAY_HOST}:{GATEWAY_PORT}")
    print(f"Poll:    every {POLL_INTERVAL}s, stale after {STALE_AFTER}s")
    print(f"History: {LOG_DB_PATH} (every {LOG_INTERVAL}s, {LOG_RETENTION_DAYS}d retention)")
    print("=" * 60)

    os.makedirs(os.path.dirname(LOG_DB_PATH), exist_ok=True)
    storage.init_db(LOG_DB_PATH)

    _test_data = load_test_data()
    if _test_data:
        print(f"[{datetime.now()}] Test data available as fallback (inverter_snapshot.json)")

    if os.path.exists(MODBUS_PORT):
        reader = InverterReader(MODBUS_PORT, MODBUS_BAUDRATE, MODBUS_DEVICE_ID)
        if reader.connect():
            _inverter = reader
        else:
            print(f"[{datetime.now()}] Could not connect to inverter -- "
                  f"will use test data if available")
    else:
        print(f"[{datetime.now()}] Modbus port {MODBUS_PORT} not found -- "
              f"will use test data if available")

    if _inverter is None and _test_data is None:
        print(f"[{datetime.now()}] WARNING: no inverter and no test data. "
              f"/latest will return 503 until the inverter is reachable.")

    _poll_thread = threading.Thread(target=_poll_loop, daemon=True)
    _poll_thread.start()

    yield

    _stop_event.set()
    if _inverter:
        _inverter.disconnect()


app = FastAPI(title="Growatt Local Gateway", lifespan=lifespan)


@app.get("/health")
def health():
    snap = state.snapshot()
    return {
        "modbus_connected": _inverter is not None,
        "has_reading": snap is not None,
        "source": snap["source"] if snap else "none",
        "age_seconds": snap["age_seconds"] if snap else None,
    }


@app.get("/latest")
def latest():
    snap = state.snapshot()
    if snap is None:
        return JSONResponse(
            status_code=503,
            content={"error": "no reading available yet"},
        )
    return snap


@app.get("/history")
def history(hours: float = 24):
    """Local durable history -- survives gateway restarts and doesn't
    depend on main-pi5's Prometheus having successfully scraped anything.
    See docs/GATEWAY.md 'Local history buffer'."""
    hours = max(1.0, min(hours, 24 * LOG_RETENTION_DAYS))
    readings = storage.get_history(LOG_DB_PATH, hours=hours)
    return {"readings": readings, "count": len(readings)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=GATEWAY_HOST, port=GATEWAY_PORT)
