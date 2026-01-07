# Growatt SPF Series - Complete Modbus Register Map

Based on **Growatt OffGrid SPF5000 Modbus RS485 RTU Protocol V0.11** (2017-08-09)

---

## Connection Parameters

| Parameter | Value |
|-----------|-------|
| Baud Rate | 9600 bps |
| Data Format | 8N1 (8 bits, No parity, 1 stop bit) |
| Device ID (USB) | 1 (default) |
| Device ID (RS485) | 1-247 (configurable) |
| Min Command Interval | 850ms (recommended: 1000ms) |
| Max Registers per Read | 45 |
| Function Codes | 0x03 (Holding), 0x04 (Input) |

---

## Input Registers (Read-Only Monitoring Data)

### System Status and Control

| Reg | Name | Description | Scaling | Unit | Example |
|-----|------|-------------|---------|------|---------|
| 0 | System Status | Operational mode | - | Code | 12 = PV Charge & Discharge |

**Status Codes:**
- `0` = Standby
- `2` = Discharge (battery → load)
- `3` = Fault
- `5` = PV Charge (solar → battery)
- `6` = AC Charge (grid → battery)
- `7` = Combine Charge (solar + grid → battery)
- `11` = Bypass (direct grid passthrough)
- `12` = PV Charge & Discharge (solar → battery + battery → load)

---

### PV (Solar) Input Registers

| Reg | Name | Description | Scaling | Unit | Example |
|-----|------|-------------|---------|------|---------|
| 1 | Vpv1 | PV1 voltage | 0.1 | V | 898 = 89.8V |
| 2 | Vpv2 | PV2 voltage | 0.1 | V | 0 = 0.0V |
| 3-4 | Ppv1 H/L | PV1 power (32-bit) | 0.1 | W | 4500 = 450.0W |
| 5-6 | Ppv2 H/L | PV2 power (32-bit) | 0.1 | W | 0 = 0.0W |
| 7 | Buck1Curr | Buck1 current | 0.1 | A | 52 = 5.2A |
| 8 | Buck2Curr | Buck2 current | 0.1 | A | 0 = 0.0A |

**Note:** 32-bit values use two consecutive registers (high word, low word)

---

### Battery Registers

| Reg | Name | Description | Scaling | Unit | Example |
|-----|------|-------------|---------|------|---------|
| 17 | Bat Volt | Battery voltage (M3) | **0.01** | V | 5320 = 53.20V |
| 18 | BatterySOC | State of charge | 1 | % | 95 = 95% |
| 28 | Bat_s_Volt | Battery port voltage (DSP) | 0.01 | V | 5322 = 53.22V |
| 29 | Bat_Volt_DSP | Battery bus voltage (DSP) | 0.01 | V | 5318 = 53.18V |
| 77-78 | Bat_Watt H/L | Battery power (signed 32-bit) | 0.1 | W | See below |

**Battery Power (Registers 77-78):**
- **Positive value** = Battery discharging (battery → inverter)
- **Negative value** = Battery charging (solar/grid → battery)
- Example: `1030` = 103.0W discharging
- Example: `-2500` = 250.0W charging

---

### AC Input (Grid/Utility) Registers

| Reg | Name | Description | Scaling | Unit | Example |
|-----|------|-------------|---------|------|---------|
| 20 | Grid Volt | AC **INPUT** voltage (from grid) | 0.1 | V | 0 = 0.0V (off-grid) |
| 21 | Line Freq | AC input frequency | 0.01 | Hz | 6000 = 60.00 Hz |
| 36-37 | AC_InWatt H/L | AC input power (32-bit) | 0.1 | W | 0 = 0.0W |
| 38-39 | AC_InVA H/L | AC input apparent power (32-bit) | 0.1 | VA | 0 = 0.0 VA |

**IMPORTANT:** When running off-grid, these registers show 0 (no grid connection)

---

### AC Output (Inverter Output) Registers ⚡

| Reg | Name | Description | Scaling | Unit | Example |
|-----|------|-------------|---------|------|---------|
| **22** | **OutputVolt** | **AC OUTPUT voltage** (to load) | 0.1 | V | 1199 = 119.9V |
| 23 | OutputFreq | AC output frequency | 0.01 | Hz | 5999 = 59.99 Hz |
| 9-10 | OP_Watt H/L | Output active power (32-bit) | 0.1 | W | 930 = 93.0W |
| 11-12 | OP_VA H/L | Output apparent power (32-bit) | 0.1 | VA | 1210 = 121.0 VA |
| 24 | Output DCV | Output DC voltage | 0.1 | V | - |
| 34 | OP_Curr | Output current | 0.1 | A | 10 = 1.0A |
| 35 | Inv_Curr | Inverter current | 0.1 | A | 9 = 0.9A |
| 27 | LoadPercent | Load percentage | **0.1** | % | 40 = 4.0% |

**CRITICAL:**
- ❌ Register 20 = Grid **INPUT** voltage (shows 0V when off-grid)
- ✅ Register 22 = Inverter **OUTPUT** voltage (shows actual house voltage!)

---

### Temperature Registers

| Reg | Name | Description | Scaling | Unit | Example |
|-----|------|-------------|---------|------|---------|
| 25 | InvTemp | Inverter temperature | 0.1 | °C | 271 = 27.1°C |
| 26 | DcDc Temp | DC-DC converter temperature | 0.1 | °C | 251 = 25.1°C |
| 32 | Buck1_NTC | Buck1 temperature | 0.1 | °C | 230 = 23.0°C |
| 33 | Buck2_NTC | Buck2 temperature | 0.1 | °C | 239 = 23.9°C |

**Normal Range:** 20-40°C (idle), up to 60°C (high load)

---

### System Information Registers

| Reg | Name | Description | Scaling | Unit | Example |
|-----|------|-------------|---------|------|---------|
| 19 | Bus Volt | DC bus voltage | 0.1 | V | 2106 = 210.6V |
| 30-31 | Time total H/L | Work time total (32-bit) | 0.5 | seconds | - |
| 40 | Fault bit | Fault code | - | Hex | 0x0000 = No fault |
| 41 | Warning bit | Warning code | - | Hex | 0x0000 = No warning |
| 44 | DTC | Device Type Code | - | Code | 034xx = SPF 3-5K |

---

### AC Charge Registers

| Reg | Name | Description | Scaling | Unit |
|-----|------|-------------|---------|------|
| 13-14 | ACChr_Watt H/L | AC charge power (32-bit) | 0.1 | W |
| 15-16 | ACChr_VA H/L | AC charge apparent power (32-bit) | 0.1 | VA |
| 68 | ACChrCurr | AC charge battery current | 0.1 | A |

---

### Energy Counters (32-bit)

| Reg | Name | Description | Scaling | Unit |
|-----|------|-------------|---------|------|
| 48-49 | Epv1_today H/L | PV1 energy today | 0.1 | kWh |
| 50-51 | Epv1_total H/L | PV1 energy total | 0.1 | kWh |
| 52-53 | Epv2_today H/L | PV2 energy today | 0.1 | kWh |
| 54-55 | Epv2_total H/L | PV2 energy total | 0.1 | kWh |
| 56-57 | Eac_chrToday H/L | AC charge energy today | 0.1 | kWh |
| 58-59 | Eac_chrTotal H/L | AC charge energy total | 0.1 | kWh |
| 60-61 | Ebat_dischrToday H/L | Battery discharge today | 0.1 | kWh |
| 62-63 | Ebat_dischrTotal H/L | Battery discharge total | 0.1 | kWh |
| 64-65 | Eac_dischrToday H/L | AC discharge today | 0.1 | kWh |
| 66-67 | Eac_dischrTotal H/L | AC discharge total | 0.1 | kWh |

---

### Battery Discharge/Charge Details

| Reg | Name | Description | Scaling | Unit |
|-----|------|-------------|---------|------|
| 69-70 | AC_DisChrWatt H/L | AC discharge power (32-bit) | 0.1 | W |
| 71-72 | AC_DisChrVA H/L | AC discharge apparent power (32-bit) | 0.1 | VA |
| 73-74 | Bat_DisChrWatt H/L | Battery discharge power (32-bit) | 0.1 | W |
| 75-76 | Bat_DisChrVA H/L | Battery discharge apparent power (32-bit) | 0.1 | VA |

---

### BMS (Battery Management System) Registers

**Registers 90-145** contain BMS data (when lithium battery with BMS is connected):

| Reg | Name | Description |
|-----|------|-------------|
| 90 | BMS_Status | Status from BMS |
| 91 | BMS_Error | Error information from BMS |
| 92 | BMS_WarnInfo | Warning info from BMS |
| 93 | BMS_SOC | SOC from BMS |
| 94 | BMS_BatteryVolt | Battery voltage from BMS (0.01V) |
| 95 | BMS_BatteryCurr | Battery current from BMS (0.1A) |
| 96 | BMS_BatteryTemp | Battery temperature from BMS (0.1°C) |
| 102-117 | BMS_Cell1-16_Volt | Individual cell voltages |

---

### Solar Charger Registers (External MPPT)

**Registers 180-224** contain data from external solar charge controllers (if connected)

---

## Holding Registers (Configuration)

**⚠️ WARNING:** Writing to holding registers can change inverter settings! Only modify if you understand the implications.

### Basic Configuration

| Reg | Name | Description | Write | Values | Default |
|-----|------|-------------|-------|--------|---------|
| 0 | On/Off | Standby/Output control | W | See below | 0x0000 |
| 1 | OutputConfig | AC output priority | W | 0=BAT, 1=PV, 2=UTI | 0 |
| 2 | ChargeConfig | Charge source | W | 0=PV first, 1=PV&UTI, 2=PV only | 0 |
| 18 | OutputVoltType | Output voltage | W | 0=208V, 1=230V, 2=240V | 1 |
| 19 | OutputFreqType | Output frequency | W | 0=50Hz, 1=60Hz | 0 |
| 30 | Com Address | Modbus address | W | 1-254 | 1 |

**On/Off Register (0) Values:**
- `0x0000` = Standby off, Output enable
- `0x0001` = Standby on, Output enable
- `0x0100` = Standby off, Output disable
- `0x0101` = Standby on, Output disable

---

### Battery Configuration

| Reg | Name | Description | Write | Range | Default |
|-----|------|-------------|-------|-------|---------|
| 34 | MaxChargeCurr | Max charge current | W | 10-130A | 70A |
| 35 | BulkChargeVolt | Bulk charge voltage | W | 500-580 (×0.1V) | 564 (56.4V) |
| 36 | FloatChargeVolt | Float charge voltage | W | 500-560 (×0.1V) | 540 (54.0V) |
| 37 | BatLowToUtiVolt | Low battery switchover | W | 444-514 (×0.1V) | 464 (46.4V) |
| 38 | FloatChargeCurr | Float charge current | W | 0-80 (×0.1A) | - |
| 39 | Battery Type | Battery chemistry | W | 0=Lead, 1=Li, 2=Custom | 1 |

**⚠️ DANGER:** Incorrect battery voltage settings can damage batteries or cause fire!

---

### Time Configuration

| Reg | Name | Description | Write | Range |
|-----|------|-------------|-------|-------|
| 3 | UtiOutStart | Utility output start hour | W | 0-23 |
| 4 | UtiOutEnd | Utility output end hour | W | 0-23 |
| 5 | UtiChargeStart | Utility charge start hour | W | 0-23 |
| 6 | UtiChargeEnd | Utility charge end hour | W | 0-23 |
| 45-50 | Sys Year/Month/Day/Hour/Min/Sec | System time | W | - |

---

### Firmware Information (Read-Only)

| Reg | Name | Description | Unit |
|-----|------|-------------|------|
| 9-11 | Fw version H/M/L | Firmware version | ASCII |
| 12-14 | Fw version2 H/M/L | Control firmware version | ASCII |
| 67-70 | FW Build No. | Firmware build number | ASCII |
| 73 | ModbusVersion | Modbus protocol version | Int (207 = V2.07) |
| 76-77 | Rate Watt H/L | Rated active power | 0.1W |
| 78-79 | Rate VA H/L | Rated apparent power | 0.1VA |

---

## Fault Codes (Register 40)

| Hex Code | Description |
|----------|-------------|
| 0x0002 | CPU A to B communication error |
| 0x0004 | Battery sample inconsistent |
| 0x0008 | BUCK over current |
| 0x0010 | BMS communication fault |
| 0x0020 | Battery abnormal |
| 0x0080 | Battery voltage high |
| 0x0100 | Over temperature |
| 0x0200 | Over load |
| 0x10000 | Battery reverse connection |
| 0x20000 | BUS soft start fail |
| 0x40000 | DC-DC abnormal |
| 0x80000 | DC voltage high |
| 0x2000000 | Output short circuit |
| 0x4000000 | Li-Battery over load |

---

## Warning Codes (Register 41)

| Hex Code | Description |
|----------|-------------|
| 0x0001 | Battery voltage low |
| 0x0002 | Over temperature warning |
| 0x0004 | Over load warning |
| 0x0008 | Fail to read EEPROM |
| 0x0010 | Firmware version mismatch |
| 0x0020 | Fail to write EEPROM |
| 0x0040 | BMS warning |
| 0x0080 | Li-Battery over load warning |
| 0x0100 | Li-Battery aging warning |
| 0x0200 | Fan lock warning |

---

## Python Reading Examples

### Read 16-bit Unsigned Register
```python
def read_u16(client, address):
    result = client.read_input_registers(address=address, count=1, device_id=1)
    return result.registers[0]

# Example: Battery SOC (register 18)
soc = read_u16(client, 18)  # No scaling needed
print(f"Battery: {soc}%")
```

### Read 32-bit Unsigned Register
```python
def read_u32(client, address):
    result = client.read_input_registers(address=address, count=2, device_id=1)
    high = result.registers[0]
    low = result.registers[1]
    return (high << 16) | low

# Example: PV1 Power (registers 3-4)
ppv1 = read_u32(client, 3) * 0.1
print(f"PV1: {ppv1:.1f}W")
```

### Read 32-bit Signed Register
```python
def read_s32(client, address):
    result = client.read_input_registers(address=address, count=2, device_id=1)
    high = result.registers[0]
    low = result.registers[1]
    val = (high << 16) | low
    if val >= 0x80000000:
        val -= 0x100000000
    return val

# Example: Battery Power (registers 77-78)
bat_watt = read_s32(client, 77) * 0.1
if bat_watt >= 0:
    print(f"Discharging: {bat_watt:.1f}W")
else:
    print(f"Charging: {abs(bat_watt):.1f}W")
```

---

## Common Mistakes

### ❌ Wrong AC Voltage Register
```python
# WRONG - This reads grid INPUT voltage
ac_volt = read_u16(client, 20) * 0.1  # Shows 0V when off-grid!
```

### ✅ Correct AC Voltage Register
```python
# CORRECT - This reads inverter OUTPUT voltage
ac_volt = read_u16(client, 22) * 0.1  # Shows actual house voltage
```

### ❌ Wrong Battery Voltage Scaling
```python
# WRONG - Battery voltage uses 0.01, not 0.1!
bat_volt = read_u16(client, 17) * 0.1  # Would show 532.0V!
```

### ✅ Correct Battery Voltage Scaling
```python
# CORRECT
bat_volt = read_u16(client, 17) * 0.01  # Shows 53.20V
```

---

## Device Type Codes (DTC)

| Code | Device Type | Note |
|------|-------------|------|
| 034xx | OffGrid | SPF 3000-5000 series |
| 001xx-010xx | Grid-tied | TL/HF/LF inverters |
| 10004 | Data logger | WiFi module |

---

**Document Version:** 1.0
**Protocol Version:** V0.11
**Last Updated:** 2026-01-07
