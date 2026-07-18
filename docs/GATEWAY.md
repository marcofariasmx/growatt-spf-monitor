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

## Configuration

New `.env` variables (see `.env.example`):

| Variable | Default | Meaning |
|---|---|---|
| `GATEWAY_HOST` | `127.0.0.1` | Bind address. Keep this localhost-only -- there's no auth on the API. |
| `GATEWAY_PORT` | `8090` | Local HTTP port. |
| `GATEWAY_POLL_INTERVAL` | `15` | Seconds between Modbus polls. |
| `GATEWAY_STALE_AFTER` | `90` | Seconds after which a cached reading is flagged `stale`. |

`MODBUS_PORT` / `MODBUS_BAUDRATE` / `MODBUS_DEVICE_ID` now only matter to
`growatt_gateway.py` -- `growatt_cloud.py` no longer reads them.

## Deployment

Two systemd services now, gateway first:

```bash
sudo cp growatt-gateway.service growatt-cloud.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now growatt-gateway
sudo systemctl enable --now growatt-cloud
```

`growatt-cloud.service` has `After=`/`Wants=growatt-gateway.service` (a soft
dependency, not `Requires=`/`BindsTo=`) -- if the gateway is momentarily
down, the relay keeps running and simply skips upload cycles until it's
back, rather than being taken down with it.

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
