#!/usr/bin/env python3
"""
One-off direct Modbus read, independent of growatt_gateway.py.

Useful for diagnosing communication problems (wrong baud, bad wiring, a
failing USB-serial adapter) with raw exceptions instead of the gateway's
cached view. Requires exclusive access to the serial port, so stop
growatt-gateway.service first:

    sudo systemctl stop growatt-gateway
    venv/bin/python tools/probe_modbus.py
    sudo systemctl start growatt-gateway
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))
from growatt_common import InverterReader, load_env

ENV = load_env()
PORT = ENV.get('MODBUS_PORT', '/dev/ttyUSB0')
BAUD = int(ENV.get('MODBUS_BAUDRATE', '9600'))
DEVICE_ID = int(ENV.get('MODBUS_DEVICE_ID', '1'))

reader = InverterReader(PORT, BAUD, DEVICE_ID)

print(f"[{datetime.now()}] attempting to open {PORT}...")
if not reader.connect():
    print("OPEN FAILED -- port is either busy (is growatt-gateway.service "
          "still running?) or the adapter/wiring is bad")
    sys.exit(1)

print(f"[{datetime.now()}] port opened OK, reading registers...")
try:
    data = reader.read_all()
    print(f"[{datetime.now()}] RAW READ RESULT:")
    print(f"  status={data['status']}")
    print(f"  vpv1={data['vpv1']*0.1:.1f}V  ppv1={data['ppv1']*0.1:.1f}W")
    print(f"  output_watt={data['output_watt']*0.1:.1f}W  output_va={data['output_va']*0.1:.1f}VA")
    print(f"  bat_volt={data['bat_volt']*0.01:.2f}V  bat_soc={data['bat_soc']}%")
finally:
    reader.disconnect()
