# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses
[Semantic Versioning](https://semver.org/).

## [1.1.0] - 2026-07-18

### Added
- `scripts/growatt_gateway.py`: a local FastAPI gateway that becomes the
  single exclusive owner of the Modbus serial connection, polling the
  inverter and exposing `GET /latest` / `GET /health` over a local-only
  HTTP API.
- `scripts/growatt_common.py`: shared `.env` loading, `InverterReader`, and
  test-data fallback, extracted out of `growatt_cloud.py` so the gateway
  and diagnostic tools don't duplicate it.
- `growatt-gateway.service` systemd unit.
- `tools/probe_modbus.py`: standalone raw-register read for diagnostics
  independent of the gateway's cache.
- `docs/GATEWAY.md`: architecture, API contract, and rationale for the
  gateway.
- Test suite under `tests/` (see below) and this changelog / `VERSION` file.
- `.env.example`: `GATEWAY_HOST`, `GATEWAY_PORT`, `GATEWAY_POLL_INTERVAL`,
  `GATEWAY_STALE_AFTER`, `GROWATT_API_TOKEN`.
- Redacted `test_data/*.example.json` fixtures for the test suite and for
  contributors who don't have their own captured snapshot yet.

### Changed
- `scripts/growatt_cloud.py` no longer opens the Modbus port directly. It
  fetches the latest reading from the gateway's HTTP API and forwards it
  to Growatt's cloud. A new `should_upload()` check skips the cloud
  upload entirely when the gateway's reading is a test-data fallback or
  stale, instead of forwarding it as if it were live.
- `growatt-cloud.service` now starts after (and wants) `growatt-gateway.service`.
- `requirements.txt`: added `fastapi`, `uvicorn`, `requests`.

### Fixed
- **Root cause of a reported dashboard "data mismatch":** two Raspberry
  Pis were both configured with the same datalogger/inverter serial and
  both relaying to server.growatt.com. One had no Modbus adapter attached
  at all and had been silently replaying a static test snapshot as live
  data for months; the other had a failing USB-to-RS485 adapter
  (`[Errno 5] Input/Output error`) whose every register read failed and
  silently returned `0` instead of raising, which also looked like
  plausible "idle inverter" data instead of a communication fault.
  `InverterReader._read_u16`/`_read_u32` now log the real Modbus
  exception/error response instead of swallowing it with a bare `except:
  pass`, and the new gateway/`should_upload()` split makes sure a
  fabricated or stale reading is never forwarded to the cloud without
  it being visible in the logs.

### Security
- Real device serial numbers (`test_data/*.json`, `*.pcap`) are now
  gitignored -- they're sufficient to impersonate a datalogger to
  Growatt's cloud and were previously untracked-but-present on deployed
  hosts, not something that belonged in a public repo. Only redacted
  `*.example.json` fixtures are committed.

## [1.0.0] - 2026-01-07

- Initial release: Modbus RTU register mapping and monitoring scripts for
  the Growatt SPF 3000TL LVM-48P, official protocol documentation, and
  the ShineWiFi-F cloud dongle emulation (`growatt_cloud.py`) built from
  captured real-dongle traffic.
