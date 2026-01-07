#!/usr/bin/env python3
"""
Growatt SPF 3000TL LVM-48P Monitoring Script
Based on official SPF Series Modbus RTU Protocol V0.11

Correct register mappings for USB connection (device_id=1)
"""

import time
from pymodbus.client import ModbusSerialClient

PORT = '/dev/ttyUSB0'
BAUD_RATE = 9600
DEVICE_ID = 1
DELAY = 1.2

# System Status codes
STATUS_CODES = {
    0: "Standby",
    1: "No Use",
    2: "Discharge",
    3: "Fault",
    4: "Flash",
    5: "PV Charge",
    6: "AC Charge",
    7: "Combine Charge",
    8: "Combine Charge & Bypass",
    9: "PV Charge & Bypass",
    10: "AC Charge & Bypass",
    11: "Bypass",
    12: "PV Charge & Discharge"
}

def read_u16(client, address):
    """Read unsigned 16-bit register."""
    try:
        result = client.read_input_registers(address=address, count=1, device_id=DEVICE_ID)
        if hasattr(result, 'registers'):
            return result.registers[0]
    except:
        pass
    return None

def read_u32(client, address):
    """Read unsigned 32-bit value (high/low registers)."""
    try:
        result = client.read_input_registers(address=address, count=2, device_id=DEVICE_ID)
        if hasattr(result, 'registers') and len(result.registers) == 2:
            high = result.registers[0]
            low = result.registers[1]
            return (high << 16) | low
    except:
        pass
    return None

def read_s32(client, address):
    """Read signed 32-bit value (for battery power)."""
    try:
        result = client.read_input_registers(address=address, count=2, device_id=DEVICE_ID)
        if hasattr(result, 'registers') and len(result.registers) == 2:
            high = result.registers[0]
            low = result.registers[1]
            val = (high << 16) | low
            # Convert to signed
            if val >= 0x80000000:
                val -= 0x100000000
            return val
    except:
        pass
    return None

def main():
    client = ModbusSerialClient(
        port=PORT,
        baudrate=BAUD_RATE,
        bytesize=8,
        parity='N',
        stopbits=1,
        timeout=3
    )

    if not client.connect():
        print(f"Failed to connect to {PORT}")
        return

    print("=" * 70)
    print("Growatt SPF 3000TL LVM-48P - Comprehensive Monitor")
    print("Using Official SPF Series Protocol V0.11")
    print("=" * 70)

    try:
        # System Status
        status = read_u16(client, 0)
        status_str = STATUS_CODES.get(status, f"Unknown ({status})")
        print(f"\nSystem Status: {status_str}")

        # === PV Input ===
        print("\n--- PV Input ---")
        vpv1 = read_u16(client, 1)
        vpv2 = read_u16(client, 2)
        ppv1 = read_u32(client, 3)
        ppv2 = read_u32(client, 5)

        if vpv1 is not None:
            print(f"PV1 Voltage:  {vpv1 * 0.1:.1f} V")
        if ppv1 is not None:
            print(f"PV1 Power:    {ppv1 * 0.1:.1f} W")
        if vpv2 is not None:
            print(f"PV2 Voltage:  {vpv2 * 0.1:.1f} V")
        if ppv2 is not None:
            print(f"PV2 Power:    {ppv2 * 0.1:.1f} W")

        buck1_curr = read_u16(client, 7)
        buck2_curr = read_u16(client, 8)
        if buck1_curr is not None:
            print(f"Buck1 Current: {buck1_curr * 0.1:.1f} A")
        if buck2_curr is not None:
            print(f"Buck2 Current: {buck2_curr * 0.1:.1f} A")

        # === Battery ===
        print("\n--- Battery ---")
        bat_volt = read_u16(client, 17)
        bat_soc = read_u16(client, 18)
        bat_watt = read_s32(client, 77)

        if bat_volt is not None:
            print(f"Battery Voltage: {bat_volt * 0.01:.2f} V")
        if bat_soc is not None:
            print(f"Battery SOC:     {bat_soc} %")
        if bat_watt is not None:
            if bat_watt >= 0:
                print(f"Battery Power:   {bat_watt * 0.1:.1f} W (Discharging)")
            else:
                print(f"Battery Power:   {abs(bat_watt) * 0.1:.1f} W (Charging)")

        # === AC Input (Grid/Utility) ===
        print("\n--- AC Input (Grid) ---")
        grid_volt = read_u16(client, 20)
        line_freq = read_u16(client, 21)
        ac_in_watt = read_u32(client, 36)
        ac_in_va = read_u32(client, 38)

        if grid_volt is not None:
            print(f"Grid Voltage:    {grid_volt * 0.1:.1f} V")
        if line_freq is not None:
            print(f"Grid Frequency:  {line_freq * 0.01:.2f} Hz")
        if ac_in_watt is not None:
            print(f"Grid Power:      {ac_in_watt * 0.1:.1f} W")
        if ac_in_va is not None:
            print(f"Grid App Power:  {ac_in_va * 0.1:.1f} VA")

        # === AC Output (INVERTER OUTPUT - THE KEY FIX!) ===
        print("\n--- AC Output (Inverter) ---")
        output_volt = read_u16(client, 22)
        output_freq = read_u16(client, 23)
        output_watt = read_u32(client, 9)
        output_va = read_u32(client, 11)
        output_curr = read_u16(client, 34)
        load_percent = read_u16(client, 27)

        if output_volt is not None:
            print(f"Output Voltage:  {output_volt * 0.1:.1f} V")
        if output_freq is not None:
            print(f"Output Frequency: {output_freq * 0.01:.2f} Hz")
        if output_watt is not None:
            print(f"Output Power:    {output_watt * 0.1:.1f} W")
        if output_va is not None:
            print(f"Output App Power: {output_va * 0.1:.1f} VA")
        if output_curr is not None:
            print(f"Output Current:  {output_curr * 0.1:.1f} A")
        if load_percent is not None:
            print(f"Load Percentage: {load_percent * 0.1:.1f} %")

        # === Temperatures ===
        print("\n--- Temperatures ---")
        inv_temp = read_u16(client, 25)
        dcdc_temp = read_u16(client, 26)
        buck1_temp = read_u16(client, 32)
        buck2_temp = read_u16(client, 33)

        if inv_temp is not None:
            print(f"Inverter Temp:   {inv_temp * 0.1:.1f} °C")
        if dcdc_temp is not None:
            print(f"DC-DC Temp:      {dcdc_temp * 0.1:.1f} °C")
        if buck1_temp is not None:
            print(f"Buck1 Temp:      {buck1_temp * 0.1:.1f} °C")
        if buck2_temp is not None:
            print(f"Buck2 Temp:      {buck2_temp * 0.1:.1f} °C")

        # === Other Useful Info ===
        print("\n--- System Info ---")
        bus_volt = read_u16(client, 19)
        inv_curr = read_u16(client, 35)

        if bus_volt is not None:
            print(f"Bus Voltage:     {bus_volt * 0.1:.1f} V")
        if inv_curr is not None:
            print(f"Inverter Current: {inv_curr * 0.1:.1f} A")

        # === Fault/Warning ===
        fault_bit = read_u16(client, 40)
        warning_bit = read_u16(client, 41)

        if fault_bit is not None and fault_bit != 0:
            print(f"\n⚠ Fault Bit: 0x{fault_bit:04X}")
        if warning_bit is not None and warning_bit != 0:
            print(f"⚠ Warning Bit: 0x{warning_bit:04X}")

        print("\n" + "=" * 70)

    except Exception as e:
        print(f"Error during monitoring: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    main()
