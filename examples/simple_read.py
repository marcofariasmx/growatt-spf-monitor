#!/usr/bin/env python3
"""
Simple Example: Read Basic Inverter Parameters
Shows minimal code to read key registers
"""

from pymodbus.client import ModbusSerialClient

PORT = '/dev/ttyUSB0'
DEVICE_ID = 1

def read_u16(client, address):
    """Read unsigned 16-bit register."""
    result = client.read_input_registers(address=address, count=1, device_id=DEVICE_ID)
    return result.registers[0]

def main():
    # Connect
    client = ModbusSerialClient(port=PORT, baudrate=9600, timeout=3)
    client.connect()

    # Read battery info
    bat_volt = read_u16(client, 17) * 0.01  # Register 17, scale 0.01
    bat_soc = read_u16(client, 18)          # Register 18, scale 1

    # Read AC output
    ac_volt = read_u16(client, 22) * 0.1    # Register 22, scale 0.1
    ac_freq = read_u16(client, 23) * 0.01   # Register 23, scale 0.01

    # Read PV input
    pv_volt = read_u16(client, 1) * 0.1     # Register 1, scale 0.1

    # Read temperature
    inv_temp = read_u16(client, 25) * 0.1   # Register 25, scale 0.1

    # Display
    print("\n=== Growatt Inverter Status ===")
    print(f"Battery:     {bat_volt:.2f}V @ {bat_soc}%")
    print(f"AC Output:   {ac_volt:.1f}V @ {ac_freq:.2f}Hz")
    print(f"PV Input:    {pv_volt:.1f}V")
    print(f"Temperature: {inv_temp:.1f}°C")
    print()

    # Close
    client.close()

if __name__ == "__main__":
    main()
