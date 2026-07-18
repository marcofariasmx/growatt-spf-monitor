#!/usr/bin/env python
"""
Shared helpers for the Growatt SPF monitor: .env loading, Modbus register
reading, and the static test-data fallback used when the inverter is
unreachable.

Used by growatt_gateway.py (the only process that should ever open the
Modbus port) and by standalone diagnostic scripts. growatt_cloud.py does
NOT import the Modbus pieces of this module -- it talks to the gateway's
HTTP API instead. See docs/GATEWAY.md for the full rationale.
"""

import os
import json
from datetime import datetime


def load_env():
    """Load KEY=VALUE pairs from the repo-root .env file."""
    env_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'
    )
    env_vars = {}
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    return env_vars


class InverterReader:
    """Reads data from a Growatt SPF inverter via Modbus RTU.

    A single instance holds the serial port exclusively for as long as it's
    connected -- a second instance pointed at the same port will fail to
    open it (pyserial takes an exclusive lock). Only one process on the
    host should ever hold this open; that's the gateway.
    """

    def __init__(self, port, baudrate, device_id):
        self.port = port
        self.baudrate = baudrate
        self.device_id = device_id
        self.client = None
        # Per-read_all() cycle counters -- lets a caller tell "every single
        # register failed" (a real communication breakdown) apart from a
        # normal reading full of legitimate zeros.
        self.reads_ok = 0
        self.reads_failed = 0

    def connect(self):
        from pymodbus.client import ModbusSerialClient
        try:
            self.client = ModbusSerialClient(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=8,
                parity='N',
                stopbits=1,
                timeout=3,
            )
            if self.client.connect():
                print(f"[{datetime.now()}] Connected to inverter on {self.port}")
                return True
            print(f"[{datetime.now()}] Failed to connect to inverter")
            return False
        except Exception as e:
            print(f"[{datetime.now()}] Modbus error: {e}")
            return False

    def disconnect(self):
        if self.client:
            self.client.close()

    def _read_u16(self, address):
        try:
            result = self.client.read_input_registers(
                address=address, count=1, device_id=self.device_id
            )
            if hasattr(result, 'registers'):
                self.reads_ok += 1
                return result.registers[0]
            print(f"[{datetime.now()}] Modbus read error at reg {address}: {result}")
        except Exception as e:
            print(f"[{datetime.now()}] Modbus exception at reg {address}: {e}")
        self.reads_failed += 1
        return 0

    def _read_u32(self, address):
        try:
            result = self.client.read_input_registers(
                address=address, count=2, device_id=self.device_id
            )
            if hasattr(result, 'registers') and len(result.registers) == 2:
                self.reads_ok += 1
                return (result.registers[0] << 16) | result.registers[1]
            print(f"[{datetime.now()}] Modbus read error at reg {address}: {result}")
        except Exception as e:
            print(f"[{datetime.now()}] Modbus exception at reg {address}: {e}")
        self.reads_failed += 1
        return 0

    def _read_s32(self, address):
        val = self._read_u32(address)
        if val >= 0x80000000:
            val -= 0x100000000
        return val

    @property
    def all_reads_failed(self):
        """True only when the last read_all() call got zero successful
        register reads -- a total communication breakdown (dead adapter,
        wrong device_id, bus fault), not just a register or two glitching.
        """
        return self.reads_failed > 0 and self.reads_ok == 0

    def read_all(self):
        """Read all relevant registers from the inverter (raw, unscaled)."""
        self.reads_ok = 0
        self.reads_failed = 0
        return {
            'status': self._read_u16(0),
            'vpv1': self._read_u16(1),
            'vpv2': self._read_u16(2),
            'ppv1': self._read_u32(3),
            'ppv2': self._read_u32(5),
            'buck1_curr': self._read_u16(7),
            'buck2_curr': self._read_u16(8),
            'output_watt': self._read_u32(9),
            'output_va': self._read_u32(11),
            'grid_charge': self._read_u32(13),
            'grid_discharge': self._read_u32(15),
            'bat_volt': self._read_u16(17),
            'bat_soc': self._read_u16(18),
            'bus_volt': self._read_u16(19),
            'bat_watt': self._read_s32(77),
            'grid_volt': self._read_u16(20),
            'grid_freq': self._read_u16(21),
            'ac_in_watt': self._read_u32(36),
            'ac_in_va': self._read_u32(38),
            'output_volt': self._read_u16(22),
            'output_freq': self._read_u16(23),
            'output_curr': self._read_u16(34),
            'inv_curr': self._read_u16(35),
            'load_percent': self._read_u16(27),
            'inv_temp': self._read_u16(25),
            'dcdc_temp': self._read_u16(26),
            'buck1_temp': self._read_u16(32),
            'buck2_temp': self._read_u16(33),
        }


def load_test_data(test_file=None):
    """Load the static captured snapshot used only when the inverter can't
    be reached at all (no port, hardware fault, etc). Never a substitute
    for a real reading in normal operation -- callers must surface that
    this is what's happening rather than pass it off as live data.

    ``test_data/inverter_snapshot.json`` contains your real device serial
    numbers, so it's gitignored and won't exist in a fresh clone -- run
    scripts/save_test_data.py once to generate your own, or pass an
    explicit ``test_file`` (e.g. the redacted .example.json, used by the
    test suite).
    """
    if test_file is None:
        test_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'test_data', 'inverter_snapshot.json'
        )
    if os.path.exists(test_file):
        with open(test_file) as f:
            snapshot = json.load(f)
            raw = snapshot.get('raw_registers', {}).get('input', [])
            if raw:
                return {
                    'status': raw[0],
                    'vpv1': raw[1],
                    'vpv2': raw[2],
                    'ppv1': (raw[3] << 16) | raw[4],
                    'ppv2': (raw[5] << 16) | raw[6],
                    'buck1_curr': raw[7],
                    'buck2_curr': raw[8],
                    'output_watt': (raw[9] << 16) | raw[10],
                    'output_va': (raw[11] << 16) | raw[12],
                    'grid_charge': (raw[13] << 16) | raw[14],
                    'grid_discharge': (raw[15] << 16) | raw[16],
                    'bat_volt': raw[17],
                    'bat_soc': raw[18],
                    'bus_volt': raw[19],
                    'grid_volt': raw[20],
                    'grid_freq': raw[21],
                    'output_volt': raw[22],
                    'output_freq': raw[23],
                    'inv_temp': raw[25],
                    'dcdc_temp': raw[26],
                    'load_percent': raw[27],
                    'buck1_temp': raw[32],
                    'buck2_temp': raw[33],
                    'output_curr': raw[34],
                    'inv_curr': raw[35],
                    'ac_in_watt': 0,
                    'ac_in_va': 0,
                    'bat_watt': (raw[77] << 16) | raw[78],
                }
    return None


def scale_reading(data):
    """Human-readable scaled values from a raw register dict.

    Scaling factors per docs/REGISTER_MAP.md: voltages x0.1V (battery
    x0.01V), powers x0.1W, frequencies x0.01Hz, temperatures x0.1C.
    """
    return {
        'status': data['status'],
        'vpv1_v': round(data['vpv1'] * 0.1, 1),
        'vpv2_v': round(data['vpv2'] * 0.1, 1),
        'ppv1_w': round(data['ppv1'] * 0.1, 1),
        'ppv2_w': round(data['ppv2'] * 0.1, 1),
        'output_w': round(data['output_watt'] * 0.1, 1),
        'output_va': round(data['output_va'] * 0.1, 1),
        'bat_volt_v': round(data['bat_volt'] * 0.01, 2),
        'bat_soc_pct': data['bat_soc'],
        'bat_watt_w': round(data['bat_watt'] * 0.1, 1),
        'bus_volt_v': round(data['bus_volt'] * 0.1, 1),
        'grid_volt_v': round(data['grid_volt'] * 0.1, 1),
        'grid_freq_hz': round(data['grid_freq'] * 0.01, 2),
        'output_volt_v': round(data['output_volt'] * 0.1, 1),
        'output_freq_hz': round(data['output_freq'] * 0.01, 2),
        'load_percent': data['load_percent'],
        'inv_temp_c': round(data['inv_temp'] * 0.1, 1),
        'dcdc_temp_c': round(data['dcdc_temp'] * 0.1, 1),
    }
