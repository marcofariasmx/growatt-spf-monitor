#!/usr/bin/env python3
"""
Connection Test Script for Growatt SPF Inverter
Tests basic Modbus communication and reads a few key registers
"""

from pymodbus.client import ModbusSerialClient
import sys

PORT = '/dev/ttyUSB0'
BAUD_RATE = 9600
DEVICE_ID = 1

def test_connection():
    """Test connection and read basic registers."""

    print("=" * 60)
    print("Growatt SPF Connection Test")
    print("=" * 60)

    print(f"\nConnecting to {PORT} at {BAUD_RATE} baud...")

    client = ModbusSerialClient(
        port=PORT,
        baudrate=BAUD_RATE,
        bytesize=8,
        parity='N',
        stopbits=1,
        timeout=3
    )

    if not client.connect():
        print(f"✗ FAILED to connect to {PORT}")
        print("\nTroubleshooting:")
        print("  1. Check USB cable is connected")
        print("  2. Verify device: ls -l /dev/ttyUSB*")
        print("  3. Check permissions: groups | grep dialout")
        print("  4. Try alternate port: /dev/ttyACM0")
        return False

    print(f"✓ Connected successfully to {PORT}")

    # Test reads
    tests_passed = 0
    tests_total = 0

    test_registers = [
        (18, "Battery SOC", 1, "%"),
        (17, "Battery Voltage", 0.01, "V"),
        (22, "AC Output Voltage", 0.1, "V"),
        (0, "System Status", 1, ""),
        (25, "Inverter Temperature", 0.1, "°C"),
        (1, "PV1 Voltage", 0.1, "V"),
        (27, "Load Percentage", 0.1, "%"),
    ]

    print("\nTesting register reads:")

    for reg, name, scale, unit in test_registers:
        tests_total += 1
        try:
            result = client.read_input_registers(address=reg, count=1, device_id=DEVICE_ID)
            if hasattr(result, 'registers'):
                value = result.registers[0] * scale
                print(f"  ✓ Register {reg:3d} ({name:20s}): {value:7.2f} {unit}")
                tests_passed += 1
            else:
                print(f"  ✗ Register {reg:3d} ({name:20s}): No response")
        except Exception as e:
            print(f"  ✗ Register {reg:3d} ({name:20s}): {e}")

    client.close()

    print("\n" + "=" * 60)
    print(f"Tests passed: {tests_passed}/{tests_total}")

    if tests_passed == tests_total:
        print("\n✓ CONNECTION TEST PASSED!")
        print("Your inverter is communicating properly.")
        return True
    elif tests_passed > 0:
        print("\n⚠ PARTIAL SUCCESS")
        print("Some registers readable, check register map for details.")
        return True
    else:
        print("\n✗ CONNECTION TEST FAILED")
        print("No registers could be read.")
        print("\nCheck:")
        print("  1. Inverter is powered on")
        print("  2. Battery voltage > 40V")
        print("  3. USB cable is good quality")
        print("  4. Device ID is correct (default: 1)")
        return False

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
