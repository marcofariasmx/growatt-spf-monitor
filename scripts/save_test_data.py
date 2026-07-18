#!/usr/bin/env python
"""Save current inverter data as test data for protocol development."""

import json
import os
import sys
from datetime import datetime
from pymodbus.client import ModbusSerialClient

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables manually
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
env_vars = {}
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()

MODBUS_PORT = env_vars.get('MODBUS_PORT', '/dev/ttyUSB0')
MODBUS_BAUDRATE = int(env_vars.get('MODBUS_BAUDRATE', 9600))
MODBUS_DEVICE_ID = int(env_vars.get('MODBUS_DEVICE_ID', 1))
DATALOGGER_SERIAL = env_vars.get('GROWATT_DATALOGGER_SERIAL', 'UNKNOWN')
INVERTER_SERIAL = env_vars.get('GROWATT_INVERTER_SERIAL', 'UNKNOWN')


def main():
    print("Connecting to inverter...")

    client = ModbusSerialClient(
        port=MODBUS_PORT,
        baudrate=MODBUS_BAUDRATE,
        bytesize=8,
        parity='N',
        stopbits=1,
        timeout=2
    )

    if not client.connect():
        print("ERROR: Failed to connect to inverter")
        sys.exit(1)

    print("Reading registers...")

    # Read input registers (0-124) - runtime data
    input_regs = client.read_input_registers(address=0, count=125, device_id=MODBUS_DEVICE_ID)
    if input_regs.isError():
        print(f"ERROR reading input registers: {input_regs}")
        client.close()
        sys.exit(1)

    # Read holding registers (0-124) - configuration (may not be supported on all inverters)
    hr = []
    try:
        holding_regs = client.read_holding_registers(address=0, count=125, device_id=MODBUS_DEVICE_ID)
        if not holding_regs.isError():
            hr = holding_regs.registers
        else:
            print("Note: Holding registers not available")
    except Exception as e:
        print(f"Note: Could not read holding registers: {e}")

    client.close()

    ir = input_regs.registers

    # Build test data structure
    test_data = {
        "timestamp": datetime.now().isoformat(),
        "datalogger_serial": DATALOGGER_SERIAL,
        "inverter_serial": INVERTER_SERIAL,
        "raw_registers": {
            "input": ir,
            "holding": hr
        },
        "parsed_values": {
            "status": ir[0],
            "pv1_voltage_V": ir[1] / 10.0,
            "pv2_voltage_V": ir[2] / 10.0,
            "pv1_power_W": ((ir[3] << 16) | ir[4]) / 10.0,
            "pv2_power_W": ((ir[5] << 16) | ir[6]) / 10.0,
            "buck1_current_A": ir[7] / 10.0,
            "buck2_current_A": ir[8] / 10.0,
            "output_power_W": ((ir[9] << 16) | ir[10]) / 10.0,
            "output_va_VA": ((ir[11] << 16) | ir[12]) / 10.0,
            "grid_charge_power_W": ((ir[13] << 16) | ir[14]) / 10.0,
            "grid_discharge_power_W": ((ir[15] << 16) | ir[16]) / 10.0,
            "battery_voltage_V": ir[17] / 100.0,
            "battery_soc_pct": ir[18],
            "bus_voltage_V": ir[19] / 10.0,
            "grid_voltage_V": ir[20] / 10.0,
            "grid_frequency_Hz": ir[21] / 100.0,
            "output_voltage_V": ir[22] / 10.0,
            "output_frequency_Hz": ir[23] / 100.0,
            "inverter_temp_C": ir[25] / 10.0,
            "dcdc_temp_C": ir[26] / 10.0,
            "load_percent": ir[27] / 10.0,
            "buck1_temp_C": ir[32] / 10.0,
            "buck2_temp_C": ir[33] / 10.0,
            "output_current_A": ir[34] / 10.0,
            "inverter_current_A": ir[35] / 10.0,
            "battery_power_W": ((ir[77] << 16) | ir[78]) / 10.0,
        }
    }

    # Save to file
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'test_data')
    os.makedirs(output_dir, exist_ok=True)

    output_file = os.path.join(output_dir, 'inverter_snapshot.json')
    with open(output_file, 'w') as f:
        json.dump(test_data, f, indent=2)

    print(f"\n{'='*60}")
    print("Test data saved successfully!")
    print(f"{'='*60}")
    print(f"\nFile: {output_file}")
    print(f"Timestamp: {test_data['timestamp']}")
    print(f"Datalogger: {DATALOGGER_SERIAL}")
    print(f"Inverter: {INVERTER_SERIAL}")
    print(f"\nInput registers: {len(ir)} values")
    print(f"Holding registers: {len(hr)} values")
    print(f"\nParsed values:")
    for key, value in test_data['parsed_values'].items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
