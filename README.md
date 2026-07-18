# Growatt SPF 3000TL LVM-48P Modbus Monitor

Complete Modbus RTU monitoring solution for Growatt SPF series off-grid solar inverters via USB connection.

## Overview

This project provides Python tools to monitor and interact with Growatt SPF 3000TL LVM-48P (48V, 3kW) off-grid solar inverters using the Modbus RTU protocol over USB.

### Supported Models
- Growatt SPF 3000TL LVM-48P (tested)
- Other Growatt SPF series inverters (should work with minor modifications)

### Key Features
- ✅ Read all inverter parameters (PV, battery, AC output, temperatures)
- ✅ Correct register mappings based on official SPF protocol V0.11
- ✅ USB connection support (via built-in USB Type-B port)
- ✅ Real-time monitoring with proper scaling factors
- ✅ System status decoding
- ✅ Fault and warning code interpretation
- ✅ Energy counters (daily and total)

## Hardware Requirements

### Inverter Connection
- **Growatt SPF 3000TL LVM-48P** inverter
- **USB Type-B cable** (standard printer cable)
- **Raspberry Pi 4** or any Linux system with USB port

### USB Connection Details
- **Built-in USB UART:** Exar XR21V1410 USB-to-UART chip
- **Device Path:** `/dev/ttyUSB0` (Linux) or `/dev/ttyACM0`
- **Baud Rate:** 9600 bps
- **Format:** 8N1 (8 data bits, No parity, 1 stop bit)
- **Device ID:** 1 (default for USB connection)

## Quick Start

### 1. Install on Raspberry Pi

```bash
# Clone or download this repository
cd ~
git clone <your-repo-url> growatt-monitor
cd growatt-monitor

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Connect Hardware

1. Connect USB Type-B cable from inverter to Raspberry Pi
2. Verify connection:
```bash
ls -l /dev/ttyUSB*
# Should show: /dev/ttyUSB0
```

### 3. Run Monitor

```bash
# Activate virtual environment
source venv/bin/activate

# Run the comprehensive monitoring script
python scripts/monitor.py
```

### Expected Output

```
======================================================================
Growatt SPF 3000TL LVM-48P - Comprehensive Monitor
Using Official SPF Series Protocol V0.11
======================================================================

System Status: PV Charge & Discharge

--- PV Input ---
PV1 Voltage:  89.8 V
PV1 Power:    450.0 W
PV2 Voltage:  0.0 V
PV2 Power:    0.0 W

--- Battery ---
Battery Voltage: 53.20 V
Battery SOC:     95 %
Battery Power:   103.0 W (Discharging)

--- AC Output (Inverter) ---
Output Voltage:  119.9 V
Output Frequency: 59.99 Hz
Output Power:    93.0 W
Output App Power: 121.0 VA
Load Percentage: 4.0 %

--- Temperatures ---
Inverter Temp:   27.1 °C
DC-DC Temp:      25.1 °C
```

## Project Structure

```
growatt-spf-monitor/
├── README.md                  # This file
├── CLAUDE.md                  # Guidance for Claude Code working in this repo
├── requirements.txt           # Python dependencies
├── .env.example                # Config template (Modbus, gateway, cloud, API token)
├── growatt-gateway.service     # systemd unit: owns the Modbus port
├── growatt-cloud.service       # systemd unit: relays to server.growatt.com
├── growatt-watchdog.service    # systemd unit: reboots the host if the gateway stays unhealthy
├── docs/
│   ├── GATEWAY.md             # Local gateway architecture + API contract
│   ├── REGISTER_MAP.md        # Complete Modbus register reference
│   ├── SPF_PROTOCOL_OFFICIAL.md # Official SPF protocol V0.11
│   ├── SETUP_GUIDE.md         # Hardware setup and installation
│   ├── TROUBLESHOOTING.md     # Common issues and solutions
│   └── TODO.md                # Future work and testing plan
├── scripts/
│   ├── growatt_gateway.py     # Owns Modbus, exposes /latest + /health, self-heals ⭐
│   ├── growatt_watchdog.py    # Reboots the host if the gateway stays unhealthy
│   ├── growatt_common.py      # Shared Modbus reading + .env loading
│   ├── growatt_cloud.py       # Relays gateway readings to Growatt cloud ⭐
│   ├── growatt_api.py         # Legacy server.growatt.com panel scraper
│   ├── monitor.py             # Standalone monitoring script (needs gateway stopped)
│   ├── test_connection.py     # Quick connection/health check
│   └── check_firmware.py      # Firmware version checker
├── tools/
│   ├── probe_modbus.py        # One-off raw register read for diagnostics
│   └── protocol_capture/      # Dongle protocol reverse-engineering toolkit
└── test_data/
    └── inverter_snapshot.json # Static fallback snapshot (gateway uses this if the inverter is unreachable)
```

## Cloud Upload & Local Gateway

Beyond local monitoring, this repo also runs a **Growatt cloud relay**: it
emulates a ShineWiFi-F dongle so a Growatt SPF inverter without one shows up
live in the ShinePhone app / server.growatt.com dashboard.

Because the Modbus port only tolerates one exclusive owner,
`growatt_gateway.py` is the single process that talks to the inverter; it
polls on an interval and exposes the latest reading over a local-only HTTP
API (`GET /latest`, `GET /health`, default `127.0.0.1:8090`).
`growatt_cloud.py` (and any future local consumer -- a dashboard, a logger,
Home Assistant) reads from that API instead of opening the serial port
itself. Full rationale and the API response shape: **[docs/GATEWAY.md](docs/GATEWAY.md)**.

```bash
# Deploy as systemd services (gateway first)
sudo cp growatt-gateway.service growatt-cloud.service growatt-watchdog.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now growatt-gateway
sudo systemctl enable --now growatt-cloud
sudo systemctl enable --now growatt-watchdog
```

The gateway self-heals from most transient faults (a soft reconnect after
a few consecutive total-read-failure cycles). For the harder case that
motivated this project -- a wedged USB-to-RS485 adapter that only a
reboot clears -- `growatt-watchdog.service` reboots the host after
sustained unhealthiness, with a cooldown so a genuinely dead adapter
doesn't reboot-loop. Details: [docs/GATEWAY.md](docs/GATEWAY.md).

## Documentation

- **[Gateway Architecture](docs/GATEWAY.md)** - Local gateway design, API contract, why it exists
- **[Register Map](docs/REGISTER_MAP.md)** - Full Modbus register reference with scaling factors
- **[SPF Protocol](docs/SPF_PROTOCOL_OFFICIAL.md)** - Official Growatt SPF protocol V0.11
- **[Setup Guide](docs/SETUP_GUIDE.md)** - Hardware setup and installation
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions
- **[TODO & Testing Plan](docs/TODO.md)** - Future work, RS485 setup, Grott integration, etc.

## Key Register Mappings

| Register | Description | Scaling | Unit |
|----------|-------------|---------|------|
| 0 | System Status | - | Status code |
| 1 | PV1 Voltage | 0.1 | V |
| 17 | Battery Voltage | 0.01 | V |
| 18 | Battery SOC | 1 | % |
| 20 | Grid Input Voltage | 0.1 | V |
| **22** | **AC Output Voltage** | 0.1 | V |
| 23 | AC Output Frequency | 0.01 | Hz |
| 25 | Inverter Temperature | 0.1 | °C |
| 27 | Load Percentage | 0.1 | % |

> **Important:** Register 20 is Grid INPUT voltage (0V when off-grid). Register 22 is the actual inverter OUTPUT voltage to your house!

## Common Issues

### No Communication
```bash
# Check USB device
ls -l /dev/ttyUSB0

# Check permissions
sudo usermod -a -G dialout $USER
# Log out and back in
```

### Wrong Readings
- Verify you're using device_id=1 for USB connection
- Check scaling factors match register map
- Ensure 1-second delay between register reads

### Device Not Found
```bash
# Install USB drivers if needed
sudo apt-get update
sudo apt-get install python3-serial
```

For more troubleshooting tips and future work, see [TODO.md](docs/TODO.md).

## Protocol Information

Based on **Growatt OffGrid SPF5000 Modbus RS485 RTU Protocol V0.11** (2017-08-09)

- **Protocol:** Modbus RTU
- **Function Codes:** 0x03 (Holding), 0x04 (Input)
- **Device Address:** 1-247 (default: 1)
- **Min Command Interval:** 850ms (recommended: 1000ms)

## Use Cases

### Home Automation
- Integrate with Home Assistant
- Monitor via MQTT
- Create dashboards with Grafana

### Data Logging
- Record energy production/consumption
- Track battery cycles
- Analyze system efficiency

### Alerting
- Low battery warnings
- Overload detection
- Temperature monitoring

## Examples

### Read Single Register
```python
from pymodbus.client import ModbusSerialClient

client = ModbusSerialClient(port='/dev/ttyUSB0', baudrate=9600)
client.connect()

# Read battery voltage (register 17)
result = client.read_input_registers(address=17, count=1, device_id=1)
voltage = result.registers[0] * 0.01
print(f"Battery: {voltage:.2f}V")

client.close()
```

### Continuous Monitoring
```python
# See examples/continuous_monitor.py for full implementation
while True:
    data = read_all_registers()
    log_to_database(data)
    time.sleep(60)  # Read every minute
```

## Running Tests

The test suite mocks the Modbus client and the gateway's in-memory cache,
so it runs without any real inverter or hardware attached:

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

See `CHANGELOG.md` for release history and `VERSION` for the current
version.

## Contributing

Contributions welcome! Please:
1. Test on your hardware
2. Document any changes
3. Follow existing code style
4. Update register map if needed

## License

MIT License - Feel free to use and modify

## Acknowledgments

- Growatt protocol documentation
- pymodbus library maintainers
- DIY solar community

## Available Scripts

### scripts/growatt_gateway.py (Cloud relay - required)
Owns the Modbus connection, polls the inverter, and serves the latest
reading over a local HTTP API. See [docs/GATEWAY.md](docs/GATEWAY.md).

**Usage:**
```bash
source venv/bin/activate
python scripts/growatt_gateway.py
```

### scripts/growatt_cloud.py (Cloud relay)
Fetches readings from the gateway and uploads them to server.growatt.com,
emulating a ShineWiFi-F dongle. Requires `growatt_gateway.py` to be running.

**Usage:**
```bash
source venv/bin/activate
python scripts/growatt_cloud.py
```

### scripts/monitor.py (Standalone Script)
Comprehensive monitoring showing all inverter data:
- PV input (voltage, power, buck currents)
- Battery status with charge/discharge detection
- AC input/output monitoring
- Temperatures and system info
- Fault/warning detection

Opens the Modbus port directly, so stop `growatt-gateway.service` first if
it's running (only one process can hold the port at a time).

**Usage:**
```bash
source venv/bin/activate
sudo systemctl stop growatt-gateway  # if running as a service
python scripts/monitor.py
```

### scripts/test_connection.py
Quick health check to verify Modbus communication is working.

**Usage:**
```bash
python scripts/test_connection.py
```

### scripts/check_firmware.py
Check current firmware version of your inverter.

**Usage:**
```bash
python scripts/check_firmware.py
```

## Support

For issues and questions:
- Review [Register Map](docs/REGISTER_MAP.md) for correct scaling
- Check [TODO.md](docs/TODO.md) for known issues and future work
- Verify hardware connections and USB permissions

## Version History

See `CHANGELOG.md` for full details.

- **v1.2.0** (2026-07-18)
  - Gateway self-heals with a soft Modbus reconnect after sustained total-read failures
  - `growatt_watchdog.py` reboots the host if that's not enough (mirrors the modem watchdog pattern)
- **v1.1.0** (2026-07-18)
  - Local gateway (`growatt_gateway.py`) as the single owner of the Modbus port
  - `growatt_cloud.py` refactored into a gateway client; skips uploads for fabricated/stale readings
  - Test suite (`pytest`), `CHANGELOG.md`, `VERSION`
- **v1.0.0** (2026-01-07)
  - Initial release
  - Complete register mapping
  - USB connection support
  - Comprehensive documentation
  - Fixed AC output voltage register (22 vs 20)

---

**Hardware Tested:**
- Growatt SPF 3000TL LVM-48P (48V, 3000VA)
- Raspberry Pi 4 Model B
- Standard USB Type-B cable

**Status:** Production Ready ✅
