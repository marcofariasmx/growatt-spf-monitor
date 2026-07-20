# Growatt SPF 3000TL LVM-48P - Future Work & Testing Plan

This document tracks all pending tasks, testing requirements, and future enhancements for the Growatt SPF monitoring system.

---

## PARKED: Automated battery charge-management for LiFePO4 longevity

**Status:** researched and documented, deliberately NOT started. Deferred
until someone can be **physically on-site at the ranch** for the first
write test, in case a charge-parameter change misbehaves. Full background
and the chemistry/balancing reasoning live in
[docs/BATTERY_CHARGE_TUNING.md](BATTERY_CHARGE_TUNING.md).

### The idea

Since the monitoring stack is already automated (gateway + Modbus + Pi),
build a scheduled charge-management routine that protects the battery
day-to-day and only stresses it when needed for balancing:

- **Normally:** charge to a lower voltage (~55.2V / 3.45V per cell) to cut
  top-of-charge stress at ~1-2% capacity cost.
- **Periodically (every ~2-4 weeks):** a full charge held at 56.8V so the
  passive BMS gets sustained high-voltage time to balance cells --
  something the current "hit 100% and cut immediately" behavior never
  provides.

### Blocker to resolve FIRST (Stage 0 — free, do before any code)

On CAN-comms SPF systems it is genuinely unknown (firmware-dependent,
conflicting forum reports) whether the inverter honors a changed charge
voltage or the BMS overrides it. **Test empirically before building
anything:** change "Charging constant voltage" 56.8 -> 55.2V via the
Growatt web dashboard Setting panel (no code needed), then watch the
gateway for 1-2 days. Does the pack now top out at 55.2V, or still reach
56.8V?

- If it takes effect -> the automation is worth building.
- If the BMS overrides it -> the knob is disconnected; abandon the project
  and leave the working BMS alone.

Do this test with someone on-site.

### Known limitations (accept before building)

- **Can't balance "only when needed" — only on a schedule.** Per-cell
  voltages (Modbus input regs 102-117) read zero on this firmware and
  aren't in the cloud data either, so imbalance can't be detected
  remotely. A fixed calendar schedule is the achievable design.
- **Benefit is modest** relative to the pack's 6000+ cycle / 10-year
  rating. Justified mainly because the infrastructure already exists and
  the change is observable + reversible, not because it's urgent.
- **Confirm battery temperature siting first** — thermal environment
  dominates LiFePO4 aging more than any voltage tweak.

### Build stages (only if Stage 0 passes)

1. **Stage 1 — Modbus write path.** `scripts/growatt_configure.py` with
   range clamps, read-back verification, and logging. Gate it behind the
   gateway (stop gateway during a write, or add write to the gateway) so
   the single-owner serial-port rule (see docs/GATEWAY.md) is respected.
2. **Stage 2 — scheduler.** A small service/cron: hold 55.2V normally,
   raise to 56.8V for one day every N weeks (balance window), return to
   55.2V, logging every change. These are persistent inverter NVRAM
   settings, so a scheduler failure is fail-safe (inverter keeps the last
   value; no real-time control loop to go wrong).
3. **Verification.** Watch one full balance window via the gateway;
   confirm the pack reaches/leaves the intended voltages.

---

## PRIORITY 1: RS485 Communication (UNRESOLVED)

### Current Status
- **Hardware**: ESP32-C3-DevKitM-1 + MAX485 module
- **Connection**: RJ45 RS485 port on inverter to MAX485 via Ethernet cable
- **Current Wiring**: Orange (pin 1) + Orange-White (pin 2)
- **Device ID**: Factory default appears to be **144** (not 1 like USB)
- **Evidence**: Background tests show "ERROR: request ask for id=1 but got id=144"

### Problem
Wiring pinout for SPF 3000TL LVM series is **NOT confirmed**. Research shows conflicting information:
- SPF Series general: Pin 1 = RS485 B, Pin 2 = RS485 A
- SPH Series: Pin 4 = B, Pin 5 = A
- MIN Series: Pin 3 = A, Pin 4 = B

### Testing Plan

#### Test 1: Verify Current Wiring with Device ID 144
**Location**: `growatt-rs485-bridge/` repository

1. Update test script to use Device ID 144:
   ```python
   DEVICE_ID = 144  # Factory default for RS485
   ```

2. Test with current Orange/Orange-White wiring:
   ```bash
   cd ~/PycharmProjects/esp32/growatt-rs485-bridge
   source venv/bin/activate
   python test/test_144_quick.py
   ```

3. Expected outcomes:
   - **Success**: Reads battery voltage, SOC, AC output correctly
   - **Failure**: Timeout, CRC errors, or no response

#### Test 2: Swap A/B Connections
If Test 1 fails, swap the A and B connections on MAX485:
- Disconnect Orange from MAX485-A and Orange-White from MAX485-B
- Connect Orange-White to MAX485-A and Orange to MAX485-B
- Retest with Device ID 144

#### Test 3: Try Different Pin Pairs
If Tests 1 and 2 fail, systematically test other Ethernet cable pin pairs:

| Test | Color Pair | Pins | MAX485 Connection |
|------|------------|------|-------------------|
| 3A | Green-White + Blue | 3 + 6 | A=Green-White, B=Blue |
| 3B | Green + Blue-White | 4 + 5 | A=Green, B=Blue-White |
| 3C | Brown-White + Brown | 7 + 8 | A=Brown-White, B=Brown |

#### Test 4: Verify with Multimeter
Use multimeter on RJ45 port (inverter OFF, batteries disconnected):
- Set to continuity/resistance mode
- Identify which pins have ~120Ω termination resistor
- Those pins are likely RS485 A and B

### Success Criteria
- Read at least 3 registers successfully (e.g., battery voltage, SOC, AC output)
- Consistent readings over 30 seconds
- No CRC errors or timeouts

### Files to Update After Success
- `growatt-rs485-bridge/README.md` - Document correct wiring
- `growatt-rs485-bridge/src/main.cpp` - Update device ID to 144
- `docs/WIRING.md` (create) - Add photos and pinout diagram

---

## PRIORITY 2: Write Functionality Implementation

### Current Status
- **Read Operations**: Fully working via USB (Device ID 1)
- **Write Operations**: Not implemented yet
- **Protocol Support**: Full read/write in SPF Protocol V0.11 docs

### Use Cases

#### 1. Inverter Control
- **Standby On/Off** (Register 0, write 1/0)
- **Output Priority** (Register 1: PV/Battery/Grid)
- **Charger Source Priority** (Register 16: Solar First/Utility First/Solar & Utility)
- **Grid Charge Enable** (Register 20: Enable/Disable)

#### 2. Charge/Discharge Settings
- **Bulk Charge Voltage** (Register 2)
- **Float Charge Voltage** (Register 3)
- **Battery Low Voltage** (Register 8)
- **Max AC Charge Current** (Register 30)

#### 3. AC Input/Output Settings
- **Output Frequency** (Register 6: 50Hz/60Hz)
- **Grid Voltage Range** (Register 17)

### Implementation Plan

#### Step 1: Create Safe Write Functions
**File**: `scripts/write_registers.py`

```python
#!/usr/bin/env python3
"""
Safe write operations for Growatt SPF 3000TL LVM-48P
Includes validation and confirmation prompts
"""

from pymodbus.client import ModbusSerialClient

def write_holding_register(client, device_id, address, value):
    """Write single holding register (function code 0x06)"""
    try:
        result = client.write_register(address, value, device_id=device_id)
        return result.isError() == False
    except Exception as e:
        print(f"Write error: {e}")
        return False

def write_multiple_registers(client, device_id, address, values):
    """Write multiple holding registers (function code 0x10)"""
    try:
        result = client.write_registers(address, values, device_id=device_id)
        return result.isError() == False
    except Exception as e:
        print(f"Write error: {e}")
        return False

# Example: Set inverter to standby mode
def set_standby(client, device_id, enable=True):
    """Set inverter standby mode (Register 0)"""
    value = 1 if enable else 0
    print(f"{'Enabling' if enable else 'Disabling'} standby mode...")
    print("WARNING: This will turn off AC output!")
    confirm = input("Type 'YES' to confirm: ")

    if confirm == 'YES':
        return write_holding_register(client, device_id, 0, value)
    else:
        print("Cancelled.")
        return False
```

#### Step 2: Safety Features
- **Read-before-write**: Always read current value first
- **Validation**: Check values are within safe ranges (per protocol doc)
- **Confirmation prompts**: Require explicit YES for critical operations
- **Logging**: Record all write operations with timestamp
- **Dry-run mode**: Test without actually writing

#### Step 3: Common Operations Scripts
Create convenience scripts:
- `scripts/set_output_priority.py` - Change PV/Battery/Grid priority
- `scripts/set_charge_settings.py` - Adjust bulk/float voltages
- `scripts/enable_grid_charge.py` - Enable/disable grid charging

#### Step 4: Testing Protocol
1. Test on non-critical registers first (e.g., output beeper)
2. Verify with read operation immediately after write
3. Test each register individually
4. Document results in `docs/WRITE_TESTING_LOG.md`

### Safety Warnings
- **NEVER** write random values to unknown registers
- **ALWAYS** refer to SPF Protocol V0.11 for valid ranges
- **TEST** on low-impact settings first
- **BACKUP** current settings by reading all holding registers

---

## PRIORITY 3: Grott Integration (Cloud Monitoring)

### What is Grott?
**GitHub**: https://github.com/johanmeijer/grott
**Purpose**: Proxy/sniffer for Growatt inverter data, intercepts traffic between WiFi dongle and Growatt servers

### How Grott Works

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│  Inverter   │◄─RS485─►│ ShineWiFi-F  │◄─WiFi──►│ Raspberry Pi│
│ SPF 3000TL  │         │   Dongle     │         │ (Grott)     │
└─────────────┘         └──────────────┘         └─────────────┘
                                                         │
                                                         ├─► Growatt Cloud
                                                         ├─► MQTT Broker
                                                         └─► InfluxDB/etc
```

### Operating Modes

#### Mode 1: Proxy/Transparent Mode (RECOMMENDED)
- Grott listens on port 5279
- WiFi dongle configured to send data to Pi IP instead of server.growatt.com
- Grott forwards data to real Growatt servers (transparent)
- Grott also publishes to local MQTT for Home Assistant/etc

**Advantages**:
- Cloud monitoring still works
- Local MQTT for real-time automation
- No modification to dongle firmware
- Non-invasive

**Configuration**:
1. Install Grott on Raspberry Pi
2. Configure WiFi dongle to point to Pi IP (via web interface or AP mode)
3. Set `grottproxy = True` in grott.ini
4. Set `ginvtype = spf` for SPF series support

#### Mode 2: Sniff Mode
- Grott listens passively on network
- Captures packets between dongle and Growatt servers
- Requires network mirroring/span port or ARP spoofing

**Advantages**:
- Zero configuration of dongle
- Works even with encrypted dongles

**Disadvantages**:
- Requires managed switch or complex networking
- More difficult setup

#### Mode 3: Direct Implementation (No Grott)
- Implement Growatt cloud protocol directly in Python
- Send data from Raspberry Pi USB monitoring to Growatt servers
- No WiFi dongle needed

**Status**: Researched, protocol is well-documented, libraries exist

### Implementation Plan: Grott Proxy Mode

#### Step 1: Install Grott on Raspberry Pi
```bash
# Option A: Docker (recommended)
docker pull ledidobe/grott:latest

# Option B: Manual installation
cd ~
git clone https://github.com/johanmeijer/grott.git
cd grott
pip3 install -r requirements.txt
```

#### Step 2: Configure Grott for SPF Series
Edit `grott.ini`:
```ini
[Generic]
ginvtype = spf
grottproxy = True
grottip = 0.0.0.0
grottport = 5279

[MQTT]
mqttip = 127.0.0.1  # or your MQTT broker IP
mqtttopic = energy/growatt
mqttauth = False    # or True with username/password
```

#### Step 3: Configure ShineWiFi-F Dongle
**Method A: Via Web Interface (if dongle supports)**
1. Connect to dongle's AP mode (usually "ShineWiFi-F-XXXXX")
2. Access web interface at 192.168.10.1 or similar
3. Change server IP from server.growatt.com to Raspberry Pi IP
4. Keep port 5279

**Method B: Via Growatt App (if available)**
- Some dongles allow server configuration via mobile app

**Method C: Via Router DNS Hijacking**
- Configure Pi as DNS server
- Resolve server.growatt.com to Pi IP
- Forces dongle to send to Pi

#### Step 4: Test and Monitor
```bash
# Run Grott in foreground to see logs
cd ~/grott
python3 grott.py -v

# Should see:
# - Inverter data being received
# - Data forwarded to Growatt cloud
# - MQTT messages published
```

#### Step 5: Integrate with Home Assistant
**MQTT Auto-Discovery** (if supported by Grott version)
- Entities automatically appear in Home Assistant

**Manual MQTT Sensors**:
```yaml
# configuration.yaml
mqtt:
  sensor:
    - name: "Solar Battery Voltage"
      state_topic: "energy/growatt"
      value_template: "{{ value_json.bat_volt }}"
      unit_of_measurement: "V"
      device_class: voltage

    - name: "Solar Battery SOC"
      state_topic: "energy/growatt"
      value_template: "{{ value_json.bat_soc }}"
      unit_of_measurement: "%"
      device_class: battery

    - name: "Solar AC Output"
      state_topic: "energy/growatt"
      value_template: "{{ value_json.output_volt }}"
      unit_of_measurement: "V"
      device_class: voltage
```

### Research Findings
- **SPF Series Support**: Confirmed working with `ginvtype = spf`
- **Docker Image**: `ledidobe/grott:2.6.1c` confirmed working for SPF 3000 TL-LVM
- **Active Development**: As of Oct 2024, still actively maintained
- **Community**: Large user base, good GitHub issue support

### Testing Checklist
- [ ] Install Grott on Raspberry Pi
- [ ] Configure for SPF series (`ginvtype = spf`)
- [ ] Configure WiFi dongle to point to Pi IP
- [ ] Verify proxy mode forwards to Growatt cloud
- [ ] Verify MQTT messages are published
- [ ] Test Home Assistant integration
- [ ] Monitor for 24 hours to ensure stability
- [ ] Document actual dongle configuration steps (model-specific)

### ShineWiFi-F Specific Notes
**Current Unknown**:
- Exact method to configure server IP on ShineWiFi-F
- Whether ShineWiFi-F has web interface or requires app
- Firmware version compatibility

**Action Item**: Research ShineWiFi-F configuration methods specifically

---

## PRIORITY 4: Direct Cloud Protocol Implementation (Alternative to Grott)

### Overview
If you want to send data directly to Growatt cloud WITHOUT using the WiFi dongle, implement the Growatt protocol from Raspberry Pi USB monitoring.

### Protocol Details (Already Researched)
- **Server**: server.growatt.com
- **Port**: 5279 (TCP)
- **Encryption**: Simple XOR with "Growatt" ASCII string
- **Packet Format**:
  ```
  [8-byte header][data payload][2-byte checksum]
  ```

### Existing Libraries
1. **Grott** (can use code from here)
2. **PyGrowatt** - Python implementation
3. **Grottserver** - Local server emulation

### Implementation Approach

#### Option A: Modify Existing Monitor Script
Add cloud forwarding to `scripts/monitor.py`:

```python
import socket
import struct

class GrowattCloudClient:
    def __init__(self, server='server.growatt.com', port=5279):
        self.server = server
        self.port = port
        self.sock = None

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.server, self.port))

    def encrypt(self, data):
        """XOR encryption with 'Growatt' string"""
        key = b'Growatt'
        return bytes([b ^ key[i % len(key)] for i, b in enumerate(data)])

    def send_data(self, inverter_data):
        """Format and send data packet"""
        # Format: Based on Grott protocol
        packet = self._build_packet(inverter_data)
        encrypted = self.encrypt(packet)
        self.sock.send(encrypted)

    def _build_packet(self, data):
        # TODO: Implement packet building based on Grott specs
        pass
```

#### Option B: Use PyGrowatt Library
```bash
pip install pygrowatt
```

```python
from pygrowatt import GrowattApi

# Initialize with your Growatt account (may need to create one)
api = GrowattApi()
api.login('username', 'password')

# Send data
api.upload_inverter_data(...)
```

### Pros and Cons

**Pros**:
- No WiFi dongle needed
- Direct control from Raspberry Pi
- Can customize data upload frequency
- No RS485 required (uses USB)

**Cons**:
- Need to reverse-engineer exact packet format for SPF series
- May violate Growatt ToS
- No official API/support
- Requires Growatt account

### Decision Point
**Recommendation**: Start with Grott proxy mode (Priority 3) because:
1. Well-tested with SPF series
2. Uses WiFi dongle as-is (no protocol reverse engineering)
3. Large community support
4. Can still keep USB monitoring running

If Grott doesn't work or WiFi dongle is problematic, then consider direct implementation.

---

## PRIORITY 5: Firmware Version Check & Updates

### Check Current Firmware

**Script Created**: `scripts/check_firmware.py`

```bash
cd ~/growatt-spf-monitor
source venv/bin/activate
python scripts/check_firmware.py
```

Reads:
- Main firmware version (Holding Registers 9-11)
- Control board firmware (Holding Registers 12-14)
- Modbus protocol version (Holding Register 73)

### Known Firmware Versions
- **502.09** - Released June 2021 (official Growatt)
- **502.10** - Found in field deployments
- **502.11** - Latest found in community reports

### Firmware Update Sources
- Watts247: https://watts247.az3.infogenixdev.com/manuals/gw/Firmware/
- Amosplanet: https://www.amosplanet.org/firmware-download-for-off-grid-inverter/

### Update Procedure (CAUTION)
**IMPORTANT**: Community recommends **NOT updating** unless fixing specific issue

1. Check current version first
2. Research if newer version fixes your specific problem
3. Download firmware file (.pak or .bin)
4. Update via:
   - USB flash drive (preferred)
   - WiFi dongle firmware update feature
   - USB cable with update software (if available)

### Documentation Needed
- [ ] Run firmware check script
- [ ] Document current version in `docs/SYSTEM_INFO.md`
- [ ] Research any known issues with current version
- [ ] Decide if update is necessary

---

## PRIORITY 6: ESP32 RS485 Bridge Improvements

### Current Project
**Location**: `growatt-rs485-bridge/`
**Hardware**: ESP32-C3-DevKitM-1 + MAX485
**Purpose**: Transparent WiFi-to-RS485 bridge

### Fixes Needed (After RS485 Wiring Resolved)

#### 1. Update Device ID to 144
**File**: `src/main.cpp`

Currently assumes Device ID 1 (USB), need to:
- Add configuration option for device ID
- Default to 144 for RS485
- Possibly scan for device ID on startup

#### 2. Auto-Discovery Feature
Add automatic device ID scanning:
```cpp
uint8_t scanForDeviceId() {
  for (uint8_t id = 1; id <= 247; id++) {
    if (queryDevice(id)) {
      return id;  // Found!
    }
    delay(10);
  }
  return 0;  // Not found
}
```

#### 3. Better Error Handling
- Implement retry logic for failed reads
- Add CRC error detection
- Report communication quality metrics

#### 4. OTA Updates
Add OTA (Over-The-Air) firmware updates:
```cpp
#include <ArduinoOTA.h>

void setupOTA() {
  ArduinoOTA.setHostname("growatt-bridge");
  ArduinoOTA.begin();
}
```

#### 5. Web Interface
Add simple web UI for:
- Current register values
- Device ID configuration
- Connection status
- Reset/reboot

### Testing Plan (After Wiring Fixed)
1. Flash updated firmware
2. Verify transparent bridging works
3. Test from Raspberry Pi connecting to ESP32 IP
4. Compare USB vs RS485 data accuracy
5. Measure latency and reliability

---

## PRIORITY 7: Home Automation Integration

### Option A: MQTT (via Grott)
Already covered in Priority 3

### Option B: Direct MQTT from Python Script
Modify `scripts/monitor.py` to publish MQTT:

```python
import paho.mqtt.client as mqtt

mqtt_client = mqtt.Client()
mqtt_client.connect("192.168.1.xxx", 1883)

# In monitoring loop:
mqtt_client.publish("energy/solar/battery_voltage", battery_voltage)
mqtt_client.publish("energy/solar/battery_soc", battery_soc)
mqtt_client.publish("energy/solar/ac_output", ac_output)
```

### Option C: RESTful API
Create Flask/FastAPI server exposing current data:

```python
from fastapi import FastAPI
app = FastAPI()

@app.get("/api/battery")
def get_battery():
    return {
        "voltage": current_voltage,
        "soc": current_soc
    }

@app.get("/api/ac_output")
def get_ac_output():
    return {
        "voltage": ac_voltage,
        "frequency": ac_freq,
        "power": ac_power
    }
```

Then integrate with Home Assistant via RESTful sensor.

### Option D: InfluxDB + Grafana
For historical data and dashboards:

```bash
# Install InfluxDB
sudo apt install influxdb influxdb-client

# Install Grafana
sudo apt install grafana
```

Modify monitoring script to write to InfluxDB:
```python
from influxdb import InfluxDBClient

influx = InfluxDBClient(host='localhost', port=8086, database='solar')

def write_data(data):
    json_body = [{
        "measurement": "solar",
        "tags": {"inverter": "spf3000"},
        "fields": {
            "battery_voltage": data['battery_voltage'],
            "battery_soc": data['battery_soc'],
            "ac_output": data['ac_output']
        }
    }]
    influx.write_points(json_body)
```

---

## PRIORITY 8: Documentation & Repository Organization

### Documents to Create

#### 1. `docs/WIRING.md`
- Photos of RJ45 connection
- Pinout diagram for SPF 3000TL LVM
- MAX485 connection diagram
- Cable color codes
- Multimeter verification procedure

#### 2. `docs/SYSTEM_INFO.md`
- Inverter model and serial number
- Current firmware version
- Battery configuration (48V, capacity, type)
- Solar panel configuration
- WiFi dongle model and firmware

#### 3. `docs/TROUBLESHOOTING.md`
- Common issues and solutions
- "No response" - check device ID, baud rate, wiring
- "CRC errors" - check A/B swap, cable quality
- "Timeout" - check power cycling, RS485 termination

#### 4. `docs/API_REFERENCE.md`
- All supported register mappings
- Read/write functions
- Example code snippets
- Safety guidelines

#### 5. `examples/` Directory
- `read_battery.py` - Simple battery status
- `read_all_sensors.py` - Complete system status
- `write_standby.py` - Control standby mode
- `continuous_monitor.py` - Loop with logging

### README Updates
Update main `README.md` with:
- Quick start guide
- Hardware requirements
- Software dependencies
- Configuration steps
- Links to detailed docs

---

## Testing Priorities Summary

**MUST DO FIRST**:
1. ✅ Check firmware version (`python scripts/check_firmware.py`)
2. 🔴 Fix RS485 wiring and verify Device ID 144 works

**HIGH PRIORITY** (After RS485 works):
3. Implement safe write functions with validation
4. Set up Grott proxy for cloud monitoring + MQTT
5. Update ESP32 bridge code for Device ID 144

**MEDIUM PRIORITY**:
6. Create MQTT publisher from monitoring script
7. Set up Home Assistant integration
8. Add InfluxDB/Grafana for historical data

**LOW PRIORITY** (Nice to have):
9. Build web interface for ESP32 bridge
10. Implement direct cloud protocol (if Grott fails)
11. Create complete documentation with photos

---

## Questions to Answer

### ShineWiFi-F Specific
- [ ] How to access configuration interface?
- [ ] Does it have web UI or requires mobile app?
- [ ] What firmware version is it running?
- [ ] Can it work in AP mode for initial setup?

### RS485 Physical Layer
- [ ] What is the exact pinout for SPF 3000TL LVM-48P?
- [ ] Is termination resistor built-in or needed externally?
- [ ] What is maximum cable length supported?
- [ ] Can multiple devices share RS485 bus?

### Protocol Clarifications
- [ ] Are there undocumented registers?
- [ ] What is update frequency for different registers?
- [ ] Are there rate limits on Modbus queries?
- [ ] Which registers require authentication/unlock?

---

## Success Metrics

### Phase 1: Complete Monitoring (USB)
- ✅ Read all sensor data via USB
- ✅ Correct register mappings verified
- ✅ Continuous monitoring stable
- ✅ Data logging functional

### Phase 2: RS485 Communication
- 🔴 Identify correct wiring pinout
- 🔴 Establish stable RS485 connection
- 🔴 Read same data as USB via RS485
- 🔴 ESP32 bridge working

### Phase 3: Control & Automation
- ⚪ Safe write operations implemented
- ⚪ Change output priority via script
- ⚪ Automated charge/discharge scheduling
- ⚪ Emergency shutdown capability

### Phase 4: Cloud & Visualization
- ⚪ Grott proxy forwarding to Growatt cloud
- ⚪ Local MQTT publishing
- ⚪ Home Assistant integration
- ⚪ Grafana dashboard

---

## Next Actions (Immediate)

1. **Run firmware check** on Raspberry Pi:
   ```bash
   cd ~/growatt-spf-monitor
   source venv/bin/activate
   python scripts/check_firmware.py
   ```

2. **Test RS485 with Device ID 144** in `growatt-rs485-bridge`:
   ```bash
   cd ~/PycharmProjects/esp32/growatt-rs485-bridge
   source venv/bin/activate
   python test/test_144_quick.py
   ```

3. **Research ShineWiFi-F configuration**:
   - Search for user manual
   - Find web interface access method
   - Identify firmware version

4. **Document current system state**:
   - Take photos of physical connections
   - Record all current settings
   - Backup current configuration

---

## Resources

### Official Documentation
- SPF Protocol V0.11: `docs/SPF_PROTOCOL_OFFICIAL.md`
- Register Mappings: `docs/REGISTER_MAP.md`

### Community Projects
- **Grott**: https://github.com/johanmeijer/grott
- **Grott Wiki**: https://github.com/johanmeijer/grott/wiki
- **PyGrowatt**: https://github.com/indykoning/PyGrowatt
- **Grottserver**: https://github.com/johanmeijer/grott (grottserver feature)

### Firmware & Manuals
- Watts247: https://watts247.az3.infogenixdev.com/manuals/gw/
- Amosplanet: https://www.amosplanet.org/

### Hardware
- MAX485 Datasheet: https://datasheets.maximintegrated.com/en/ds/MAX1487-MAX491.pdf
- ESP32-C3 Datasheet: https://www.espressif.com/sites/default/files/documentation/esp32-c3_datasheet_en.pdf

---

**Last Updated**: 2026-01-07
**Status**: RS485 wiring investigation in progress
