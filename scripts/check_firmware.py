#!/usr/bin/env python3
"""
Check Growatt SPF 3000TL LVM-48P Firmware Version
Reads firmware version from holding registers
"""

from pymodbus.client import ModbusSerialClient

PORT = '/dev/ttyUSB0'  # Adjust if needed
BAUD_RATE = 9600
DEVICE_ID = 1  # USB connection

def read_u16(client, address):
    """Read unsigned 16-bit register."""
    try:
        result = client.read_holding_registers(address=address, count=1, device_id=DEVICE_ID)
        if hasattr(result, 'registers'):
            return result.registers[0]
    except:
        pass
    return None

def main():
    print("=" * 70)
    print("Growatt SPF 3000TL LVM-48P - Firmware Version Check")
    print("=" * 70)

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

    print(f"✓ Connected to {PORT}\n")

    # Read firmware version registers (Holding Registers 9-11)
    print("Reading Firmware Version (Holding Registers 9-11)...")
    fw_h = read_u16(client, 9)   # Firmware version High
    fw_m = read_u16(client, 10)  # Firmware version Middle
    fw_l = read_u16(client, 11)  # Firmware version Low

    print(f"\nFirmware Version Registers:")
    print(f"  Register 9 (High):   {fw_h if fw_h is not None else 'N/A'}")
    print(f"  Register 10 (Middle): {fw_m if fw_m is not None else 'N/A'}")
    print(f"  Register 11 (Low):    {fw_l if fw_l is not None else 'N/A'}")

    # Try to decode as ASCII
    if fw_h is not None and fw_m is not None and fw_l is not None:
        try:
            # Each register is 2 bytes (ASCII characters)
            version_str = ""
            for val in [fw_h, fw_m, fw_l]:
                high_byte = (val >> 8) & 0xFF
                low_byte = val & 0xFF
                if high_byte != 0:
                    version_str += chr(high_byte)
                if low_byte != 0:
                    version_str += chr(low_byte)

            print(f"\nDecoded Version: {version_str}")
        except:
            print("\nCould not decode as ASCII")

    # Read Control Firmware version (Holding Registers 12-14)
    print("\n" + "-" * 70)
    print("Reading Control Board Firmware (Holding Registers 12-14)...")
    fw2_h = read_u16(client, 12)  # Control firmware High
    fw2_m = read_u16(client, 13)  # Control firmware Middle
    fw2_l = read_u16(client, 14)  # Control firmware Low

    print(f"\nControl Firmware Registers:")
    print(f"  Register 12 (High):   {fw2_h if fw2_h is not None else 'N/A'}")
    print(f"  Register 13 (Middle): {fw2_m if fw2_m is not None else 'N/A'}")
    print(f"  Register 14 (Low):    {fw2_l if fw2_l is not None else 'N/A'}")

    # Try to decode control firmware
    if fw2_h is not None and fw2_m is not None and fw2_l is not None:
        try:
            version_str2 = ""
            for val in [fw2_h, fw2_m, fw2_l]:
                high_byte = (val >> 8) & 0xFF
                low_byte = val & 0xFF
                if high_byte != 0:
                    version_str2 += chr(high_byte)
                if low_byte != 0:
                    version_str2 += chr(low_byte)

            print(f"\nDecoded Control Version: {version_str2}")
        except:
            print("\nCould not decode as ASCII")

    # Read Modbus Protocol Version (Holding Register 73)
    print("\n" + "-" * 70)
    print("Reading Modbus Protocol Version (Holding Register 73)...")
    modbus_ver = read_u16(client, 73)

    if modbus_ver is not None:
        print(f"\nModbus Protocol Version: {modbus_ver} (V{modbus_ver/100:.2f})")
        print(f"Example: 207 = V2.07, 11 = V0.11")

    print("\n" + "=" * 70)
    client.close()

if __name__ == "__main__":
    main()
