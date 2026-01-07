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

# Run the monitoring script
python monitor.py
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
├── README.md                 # This file
├── requirements.txt          # Python dependencies
├── monitor.py               # Main monitoring script
├── docs/
│   ├── REGISTER_MAP.md      # Complete Modbus register reference
│   ├── SETUP_GUIDE.md       # Detailed step-by-step setup
│   └── TROUBLESHOOTING.md   # Common issues and solutions
├── examples/
│   ├── simple_read.py       # Basic register reading example
│   ├── continuous_monitor.py # Continuous monitoring with logging
│   └── export_csv.py        # Export data to CSV
└── scripts/
    └── test_connection.py   # Connection testing utility
```

## Documentation

- **[Setup Guide](docs/SETUP_GUIDE.md)** - Complete installation instructions from scratch
- **[Register Map](docs/REGISTER_MAP.md)** - Full Modbus register reference
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Common issues and solutions

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

See [Troubleshooting Guide](docs/TROUBLESHOOTING.md) for more details.

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

## Support

For issues and questions:
- Check [Troubleshooting Guide](docs/TROUBLESHOOTING.md)
- Review register map for correct scaling
- Verify hardware connections

## Version History

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
