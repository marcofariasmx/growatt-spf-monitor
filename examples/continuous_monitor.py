#!/usr/bin/env python3
"""
Continuous Monitoring Example
Logs inverter data every minute to console and CSV file
"""

import time
import csv
from datetime import datetime
from pymodbus.client import ModbusSerialClient

PORT = '/dev/ttyUSB0'
DEVICE_ID = 1
INTERVAL = 60  # seconds between readings
CSV_FILE = 'growatt_log.csv'

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
    """Read unsigned 32-bit value."""
    try:
        result = client.read_input_registers(address=address, count=2, device_id=DEVICE_ID)
        if hasattr(result, 'registers') and len(result.registers) == 2:
            high = result.registers[0]
            low = result.registers[1]
            return (high << 16) | low
    except:
        pass
    return None

def read_inverter_data(client):
    """Read all key inverter parameters."""
    data = {
        'timestamp': datetime.now().isoformat(),
        'bat_volt': None,
        'bat_soc': None,
        'pv1_volt': None,
        'pv1_power': None,
        'ac_volt': None,
        'ac_power': None,
        'load_pct': None,
        'inv_temp': None,
    }

    # Battery
    bat_volt = read_u16(client, 17)
    if bat_volt is not None:
        data['bat_volt'] = bat_volt * 0.01

    bat_soc = read_u16(client, 18)
    if bat_soc is not None:
        data['bat_soc'] = bat_soc

    # PV
    pv1_volt = read_u16(client, 1)
    if pv1_volt is not None:
        data['pv1_volt'] = pv1_volt * 0.1

    pv1_power = read_u32(client, 3)
    if pv1_power is not None:
        data['pv1_power'] = pv1_power * 0.1

    # AC Output
    ac_volt = read_u16(client, 22)
    if ac_volt is not None:
        data['ac_volt'] = ac_volt * 0.1

    ac_power = read_u32(client, 9)
    if ac_power is not None:
        data['ac_power'] = ac_power * 0.1

    load_pct = read_u16(client, 27)
    if load_pct is not None:
        data['load_pct'] = load_pct * 0.1

    # Temperature
    inv_temp = read_u16(client, 25)
    if inv_temp is not None:
        data['inv_temp'] = inv_temp * 0.1

    return data

def main():
    print("=" * 70)
    print("Growatt SPF Continuous Monitor")
    print(f"Logging to: {CSV_FILE}")
    print(f"Interval: {INTERVAL} seconds")
    print("Press Ctrl+C to stop")
    print("=" * 70)

    # Connect
    client = ModbusSerialClient(
        port=PORT,
        baudrate=9600,
        bytesize=8,
        parity='N',
        stopbits=1,
        timeout=3
    )

    if not client.connect():
        print(f"Failed to connect to {PORT}")
        return

    print("Connected successfully\n")

    # Create CSV file with headers
    csv_exists = False
    try:
        with open(CSV_FILE, 'r') as f:
            csv_exists = True
    except:
        pass

    if not csv_exists:
        with open(CSV_FILE, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'bat_volt', 'bat_soc', 'pv1_volt', 'pv1_power',
                'ac_volt', 'ac_power', 'load_pct', 'inv_temp'
            ])

    try:
        while True:
            # Read data
            data = read_inverter_data(client)

            # Display
            print(f"\n[{data['timestamp']}]")
            print(f"  Battery:  {data['bat_volt']:.2f}V @ {data['bat_soc']}%")
            print(f"  PV:       {data['pv1_volt']:.1f}V, {data['pv1_power']:.0f}W")
            print(f"  AC Out:   {data['ac_volt']:.1f}V, {data['ac_power']:.0f}W ({data['load_pct']:.1f}%)")
            print(f"  Temp:     {data['inv_temp']:.1f}°C")

            # Log to CSV
            with open(CSV_FILE, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    data['timestamp'],
                    data['bat_volt'],
                    data['bat_soc'],
                    data['pv1_volt'],
                    data['pv1_power'],
                    data['ac_volt'],
                    data['ac_power'],
                    data['load_pct'],
                    data['inv_temp']
                ])

            # Wait
            time.sleep(INTERVAL)

    except KeyboardInterrupt:
        print("\n\nStopping monitor...")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        client.close()
        print("Disconnected")
        print(f"Data saved to: {CSV_FILE}")

if __name__ == "__main__":
    main()
