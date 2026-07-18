# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Growatt SPF Monitor is a Raspberry Pi-based solution that monitors Growatt SPF series inverters via Modbus RTU and emulates a ShineWiFi-F cloud dongle to upload inverter data to Growatt servers. This enables real-time monitoring in the ShinePhone app without the physical dongle.

## Commands

```bash
# Setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run the local gateway (owns the Modbus port, must run first/always)
python scripts/growatt_gateway.py

# Run cloud upload service (reads from the gateway, not the port directly)
python scripts/growatt_cloud.py

# One-off raw Modbus read (stop the gateway first, see docs/GATEWAY.md)
python tools/probe_modbus.py

# Query Growatt Open API to verify what the cloud is receiving
curl -H "token: $GROWATT_API_TOKEN" https://openapi.growatt.com/v1/device/list?plant_id=...

# Run the test suite (no hardware needed -- everything is mocked/fixtured)
pip install -r requirements-dev.txt
pytest

# Systemd service management
sudo systemctl start growatt-gateway.service growatt-cloud.service growatt-watchdog.service
sudo journalctl -u growatt-gateway.service -u growatt-cloud.service -u growatt-watchdog.service -f
```

## Architecture

```
Growatt SPF Inverter (USB Type-B)
         ↓ Modbus RTU (9600 baud, device_id=1) -- single exclusive owner
growatt_gateway.py (FastAPI, 127.0.0.1:8090)
         ↓ GET /latest (local HTTP)
growatt_cloud.py
         ↓ TCP Port 5279 (XOR encrypted)
Growatt Cloud (server.growatt.com)
         ↓
ShinePhone App / openapi.growatt.com (v1 API)
```

The Modbus port only tolerates one exclusive owner, so `growatt_gateway.py`
is the only process that ever opens it. Everything else -- the cloud relay,
any future local dashboard or logger -- reads the cached latest value over
HTTP. Full rationale and API contract: `docs/GATEWAY.md`.

### Core Components

- **scripts/growatt_gateway.py** - Owns the Modbus connection, polls the inverter, exposes `/latest` + `/health`, self-heals with a soft reconnect after sustained read failures
- **scripts/growatt_watchdog.py** - Reboots the host if the gateway stays unhealthy longer than a soft reconnect can fix (mirrors `huawei-monitor/watchdog.py`)
- **scripts/growatt_common.py** - Shared Modbus reading + `.env` loading + test-data fallback, used by the gateway and diagnostic tools
- **scripts/growatt_cloud.py** - Fetches readings from the gateway, encrypts payloads, uploads to cloud
- **scripts/monitor.py** - Standalone Modbus reading without cloud upload (needs the gateway stopped first)
- **scripts/growatt_api.py** - Legacy scraper against server.growatt.com's internal panel endpoints; superseded by the Open API token flow above where possible
- **tools/probe_modbus.py** - One-off raw register read for diagnostics, independent of the gateway's cache

### Cloud Protocol

- **Encryption**: XOR with 7-byte mask `"Growatt"`
- **Packet structure**: `[TID:2][PID:2][Length:2][UID:1][Type:1][Encrypted_Payload][CRC:2]`
- **Message types**: ANNOUNCE (0x03), DATA (0x04), PING (0x16), CONFIG (0x18), IDENTIFY (0x19)
- **Timing**: DATA packets every 5 minutes, PING every 3 minutes

### Boot Sequence

1. Send PING → Receive IDENTIFY request → Send IDENTIFY response
2. Send ANNOUNCE (349 bytes) → Receive ACK
3. Send 3x IDENTIFY config packets → Enter run phase

## Key Technical Details

- **Modbus delays**: Require >850ms between requests (inverter limitation)
- **Battery power sign**: Positive = Discharging, Negative = Charging
- **Output voltage**: Use register 22 (not register 20, which is grid input)
- **Device ID**: USB uses ID 1; RS485 may use ID 144
- **Payload size**: 349 bytes for both ANNOUNCE and DATA packets

### Register Scaling

- Voltage registers: ×0.1 V (except battery: ×0.01 V)
- Power registers: ×0.1 W (32-bit for PV power)
- Temperature: ×0.1 °C
- SOC: Direct percentage

## Configuration

Copy `.env.example` to `.env` and configure:
- `GROWATT_DATALOGGER_SERIAL` - ShineWiFi-F dongle serial to emulate
- `GROWATT_INVERTER_SERIAL` - SPF inverter serial number
- `MODBUS_PORT` - Serial port (default: /dev/ttyUSB0), used by growatt_gateway.py only
- `GATEWAY_HOST` / `GATEWAY_PORT` - local API bind address (default: 127.0.0.1:8090)
- `GATEWAY_POLL_INTERVAL` / `GATEWAY_STALE_AFTER` - polling cadence and staleness threshold

## Protocol Capture Tool

For reverse engineering the dongle protocol, use the capture tool in `tools/protocol_capture/`:

```bash
# Capture dongle traffic (run 24+ hours)
cd tools/protocol_capture
sudo python capture.py 192.168.50.145

# Analyze captured data
python analyze.py

# Validate Pi packets against ground truth
python compare.py data/
```

See `tools/protocol_capture/README.md` for full documentation.

## Documentation

- `docs/GATEWAY.md` - Local gateway architecture, API contract, why it exists
- `docs/REGISTER_MAP.md` - Complete Modbus register reference
- `docs/SPF_PROTOCOL_OFFICIAL.md` - Cloud protocol specification
- `docs/SETUP_GUIDE.md` - Hardware setup and installation
- `docs/TROUBLESHOOTING.md` - Common issues and solutions
- `tools/protocol_capture/README.md` - Protocol capture and analysis tool
