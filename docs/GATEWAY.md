# Local Gateway Architecture

## Why this exists

Originally `growatt_cloud.py` opened the Modbus serial port itself, read the
inverter, and relayed straight to `server.growatt.com`. That has two
problems, both of which caused a real incident on 2026-07-17:

1. **The serial port only tolerates one owner.** pyserial takes an
   exclusive lock on the port. Any second process (a diagnostic script, a
   second relay instance, a future local dashboard) that tries to open
   `/dev/ttyUSB0` while `growatt_cloud.py` holds it fails immediately with
   `Could not exclusively lock port`. There was no way to add a second
   consumer of inverter data without fighting over the bus.

2. **Silent failure looked like real data.** When the Modbus port couldn't
   be opened (or every register read failed), the old code fell back to
   replaying a static captured snapshot (`test_data/inverter_snapshot.json`)
   as if it were live -- with no signal anywhere that this was happening.
   One Pi ran for three months sending that fabricated snapshot to
   server.growatt.com; a second Pi with a genuinely failing USB adapter did
   the same thing once its Modbus reads started timing out and returning
   zero. Both looked "fine" on the cloud dashboard until compared side by
   side against a direct register read.

## Design

```
                    ┌─────────────────────────┐
                    │   Growatt SPF Inverter   │
                    └────────────┬─────────────┘
                                 │ Modbus RTU (9600 baud, exclusive)
                                 ▼
                    ┌─────────────────────────┐
                    │   growatt_gateway.py     │  <- only process that
                    │   (FastAPI, port 8090,   │     ever opens the
                    │    localhost only)       │     serial port
                    └────────────┬─────────────┘
                                 │ GET /latest, /health (HTTP, localhost)
                 ┌───────────────┼────────────────────┐
                 ▼                                     ▼
    ┌─────────────────────────┐          ┌─────────────────────────────┐
    │   growatt_cloud.py       │          │  future local consumers     │
    │   (relays to             │          │  (dashboard, logging, HA…)  │
    │    server.growatt.com)   │          └─────────────────────────────┘
    └─────────────────────────┘
```

`growatt_gateway.py` polls the inverter every `GATEWAY_POLL_INTERVAL`
seconds (default 15s) and caches the latest reading in memory. Everything
else on the box talks to it over plain HTTP instead of touching the serial
port. Only one process ever needs exclusive access; any number of local
clients can read the cached result concurrently.

If the inverter is unreachable (port missing, hardware fault, comms
timeout), the gateway falls back to the static test snapshot **but says so
explicitly** in every response (`"source": "test_data"`). `growatt_cloud.py`
checks that field and **skips the cloud upload** for that cycle rather than
forwarding fabricated numbers -- the dashboard goes stale/quiet instead of
showing a plausible-looking lie. This is the actual fix for the original
"data mismatch" report.

## API contract

### `GET /latest`

```json
{
  "raw_registers": { "status": 12, "vpv1": 764, "ppv1": 1120, "...": "..." },
  "reading": {
    "status": 12,
    "vpv1_v": 76.4, "ppv1_w": 112.0,
    "output_w": 72.0, "output_va": 121.0,
    "bat_volt_v": 53.51, "bat_soc_pct": 96, "bat_watt_w": -16.0,
    "...": "..."
  },
  "timestamp": "2026-07-17T18:10:23.932157+00:00",
  "age_seconds": 4.2,
  "stale": false,
  "source": "modbus"
}
```

- `raw_registers` -- unscaled values straight off the inverter, same shape
  `InverterReader.read_all()` has always returned. Use this if you need to
  reproduce the cloud protocol's exact register math.
- `reading` -- the same values scaled to volts/watts/percent per
  `docs/REGISTER_MAP.md`. Use this for anything human-facing.
- `source` -- `"modbus"` (real reading) or `"test_data"` (fallback
  snapshot -- **not live, treat as fake**).
- `stale` -- `true` once `age_seconds` exceeds `GATEWAY_STALE_AFTER`
  (default 90s, i.e. missed several poll cycles). A consumer should treat
  a stale reading the same as `test_data`: don't present it as current.
- Returns HTTP 503 if there's no reading at all yet (gateway just started
  and hasn't completed its first poll, or there's never been a working
  inverter connection or test snapshot).

### `GET /health`

```json
{"modbus_connected": true, "has_reading": true, "source": "modbus", "age_seconds": 4.2}
```

Quick liveness check -- doesn't require the caller to unpack `/latest`.

### `GET /history?hours=24`

```json
{"readings": [{"timestamp": "2026-07-24T12:00:00+00:00", "bat_soc_pct": 96, "...": "..."}], "count": 288}
```

The local durable history (see "Local history buffer" below), oldest first.
Only real, fresh readings ever land here -- never `test_data`.

## Configuration

New `.env` variables (see `.env.example`):

| Variable | Default | Meaning |
|---|---|---|
| `GATEWAY_HOST` | `127.0.0.1` | Bind address. Keep this localhost-only -- there's no auth on the API. |
| `GATEWAY_PORT` | `8090` | Local HTTP port. |
| `GATEWAY_POLL_INTERVAL` | `15` | Seconds between Modbus polls. |
| `GATEWAY_STALE_AFTER` | `90` | Seconds after which a cached reading is flagged `stale`. |
| `GATEWAY_LOG_DB` | `data/solar_history.db` | Path to the local durable SQLite history (see below). |
| `GATEWAY_LOG_INTERVAL` | `60` | Minimum seconds between local history writes. |
| `GATEWAY_LOG_RETENTION_DAYS` | `180` | Rows older than this are pruned once a day. |

`MODBUS_PORT` / `MODBUS_BAUDRATE` / `MODBUS_DEVICE_ID` now only matter to
`growatt_gateway.py` -- `growatt_cloud.py` no longer reads them.

## Deployment

Three systemd services now, gateway first:

```bash
sudo cp growatt-gateway.service growatt-cloud.service growatt-watchdog.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now growatt-gateway
sudo systemctl enable --now growatt-cloud
sudo systemctl enable --now growatt-watchdog
```

`growatt-cloud.service` has `After=`/`Wants=growatt-gateway.service` (a soft
dependency, not `Requires=`/`BindsTo=`) -- if the gateway is momentarily
down, the relay keeps running and simply skips upload cycles until it's
back, rather than being taken down with it. `growatt-watchdog.service` is
independent of both and can reboot the host even if `growatt-cloud` is
down for unrelated reasons -- see "Self-healing and the watchdog" below.

## Self-healing and the watchdog

The 2026-07-17 incident's root fix on rancho-inverter-pi required a full
Pi reboot: the USB-to-RS485 adapter had wedged at the kernel/USB level
(`urb stopped: -32`, then `[Errno 5] Input/Output error`), and neither a
pyserial-level reconnect nor a driver unbind/rebind cleared it. Two
complementary layers of recovery now exist, matched to what each is
actually capable of fixing:

1. **Soft reconnect (in-process, `growatt_gateway.py`).** Every
   `read_all()` cycle tracks how many of its register reads succeeded vs.
   failed (`InverterReader.all_reads_failed`). A *total* failure --
   every single register in the cycle, not just one -- counts against
   `GATEWAY_RECONNECT_AFTER_FAILURES` (default 3) consecutive cycles;
   past that, the gateway closes and reopens the serial connection
   itself. The poll loop also keeps checking for the adapter if it wasn't
   present at startup (`_try_late_connect`), so a replug or a boot-time
   race resolves on its own without a service restart. This recovers
   transient faults: a brief RS485 glitch, the inverter power-cycling,
   the port not being ready yet when the service started.

2. **Reboot watchdog (`growatt_watchdog.py`, separate process).** Polls
   the gateway's `/health` every `GATEWAY_WATCHDOG_INTERVAL` (default
   60s). After `GATEWAY_WATCHDOG_FAILURE_LIMIT` (default 10) consecutive
   unhealthy checks -- meaning the soft reconnect above has clearly not
   fixed things -- it reboots the Pi (`sudo reboot`; `mafx` has
   passwordless sudo on this host). A cooldown
   (`GATEWAY_WATCHDOG_COOLDOWN`, default 3600s) blocks a second reboot
   within an hour of the last one, so a genuinely dead adapter surfaces
   as "still unhealthy after a reboot" instead of a reboot loop. This
   mirrors the existing `huawei-monitor/watchdog.py` pattern on
   rancho-main-pi (ping failures -> modem reboot) -- same shape of
   problem, same shape of fix.

"Healthy" is intentionally strict and matches `should_upload()`'s
definition in `growatt_cloud.py`: `modbus_connected` true, `source ==
"modbus"`, and `age_seconds` under `GATEWAY_WATCHDOG_UNHEALTHY_AGE`
(default 300s). A gateway quietly serving `test_data` counts as
unhealthy here on purpose -- that silent substitution is exactly what
caused the original incident.

Deploy the watchdog as a third systemd service, after the gateway:

```bash
sudo cp growatt-watchdog.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now growatt-watchdog
```

## Local history buffer

Until 2026-07-24, the gateway only ever cached the single most recent
reading in memory (`GatewayState`) -- restart the process and it's gone.
The *only* local historical record of solar data was main-pi5's Prometheus,
which scrapes this Pi's `node_exporter` textfile collector every 5 min over
Tailscale. That's a real gap: Prometheus is pull-based, so a network blip
between this Pi and main-pi5 during a scrape produces a **permanent** hole
in its timeline -- there's no retry or backfill on that side, unlike
`growatt_cloud.py`'s relay to `server.growatt.com` (that connection just
keeps reconnecting and resumes live streaming) or `enviro-cam`'s sender on
rancho-cam-pi (which queues locally and drains the backlog once the push
to main-pi5 succeeds again).

`growatt_storage.py` closes that gap with its own durable log, independent
of anything downstream:

- Every poll cycle that gets a real reading (`source == "modbus"`, never
  `test_data` -- same discipline as `should_upload()`) is written to a local
  SQLite file (`GATEWAY_LOG_DB`, default `data/solar_history.db`), throttled
  to `GATEWAY_LOG_INTERVAL` (default 60s -- decoupled from the 15s poll
  interval on purpose; logging every poll would be ~5700 SD-card writes/day
  for no real benefit, and this fleet has SD-corruption history elsewhere).
- Rows older than `GATEWAY_LOG_RETENTION_DAYS` (default 180) are pruned once
  a day. At ~1,440 rows/day and ~150 bytes/row that's roughly 40 MB for the
  full retention window -- trivial for the SD card.
- `GET /history?hours=` exposes it, mirroring `monitor-cam-webapp`'s
  `/api/sensors/history` shape (`{"readings": [...], "count": N}`), oldest
  first, columns named to match `scale_reading()`'s keys 1:1 so a row can be
  cross-referenced against a `homelab_solar_*` Prometheus sample directly.

This does **not** attempt to backfill Prometheus itself after an outage --
Prometheus's pull model makes that impractical without remote-write and an
out-of-order ingestion window, neither of which this fleet runs, and it
would be a disproportionate amount of machinery for a rare, short, and
already-externally-backed-up gap (Growatt's own cloud still has it via
`growatt_cloud.py`, separately). The point of this buffer is simpler: the
reading itself is never actually lost, full stop, and is queryable locally
the moment anyone needs it -- whether that's a manual recovery, a future
local dashboard, or a one-off script.

## Diagnostics

`tools/probe_modbus.py` still exists for a raw, one-off Modbus read when
you need to bypass the gateway's cache entirely (e.g. to independently
verify a register value). It needs the same exclusive port access the
gateway does, so stop the gateway first:

```bash
sudo systemctl stop growatt-gateway
venv/bin/python tools/probe_modbus.py
sudo systemctl start growatt-gateway
```

`scripts/monitor.py`, `scripts/test_connection.py`, and
`scripts/check_firmware.py` are older standalone tools with the same
constraint -- they open the port directly and will fail with "could not
exclusively lock port" while the gateway is running.
