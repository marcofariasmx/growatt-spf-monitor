#!/usr/bin/env python
"""
Growatt Cloud Upload Script

Sends inverter data directly to Growatt servers, emulating a ShineWiFi-F dongle.
Based on captured packet analysis from real dongle traffic.

Protocol: TCP to server.growatt.com:5279
Format: Protocol ID 6 (XOR encrypted with "Growatt")

Packet structure:
  [tid:2][pid:2][len:2][uid:1][type:1][encrypted_payload][crc:2]

This script does NOT talk to the inverter directly -- it fetches the
latest reading from growatt_gateway.py's local HTTP API. The Modbus port
only tolerates one exclusive owner, and the gateway is it. See
docs/GATEWAY.md for why.
"""

import os
import socket
import struct
import time
import json
import urllib.request
import urllib.error
from datetime import datetime

from growatt_common import load_env

ENV = load_env()

# Configuration from environment
DATALOGGER_SERIAL = ENV.get('GROWATT_DATALOGGER_SERIAL', '')
INVERTER_SERIAL = ENV.get('GROWATT_INVERTER_SERIAL', '')
GROWATT_SERVER = ENV.get('GROWATT_SERVER', 'server.growatt.com')
GROWATT_PORT = int(ENV.get('GROWATT_PORT', '5279'))

GATEWAY_HOST = ENV.get('GATEWAY_HOST', '127.0.0.1')
GATEWAY_PORT = int(ENV.get('GATEWAY_PORT', '8090'))
GATEWAY_URL = f"http://{GATEWAY_HOST}:{GATEWAY_PORT}/latest"

# Timing (matching real dongle behavior)
DATA_INTERVAL = 300  # 5 minutes - matches real dongle
PING_INTERVAL = 180  # 3 minutes - keepalive heartbeat

# Protocol constants (from captured traffic analysis)
XOR_MASK = b'Growatt'
PROTOCOL_ID = 0x0006  # Encrypted protocol
UNIT_ID = 0x01

# Message types (from captured boot sequence)
MSG_TYPE_ANNOUNCE = 0x03  # Data announcement (NOT 0x04!)
MSG_TYPE_DATA = 0x04      # Alternative data type (not used by ShineWiFi-F)
MSG_TYPE_PING = 0x16      # Keepalive heartbeat
MSG_TYPE_CONFIG = 0x18    # Configuration
MSG_TYPE_IDENTIFY = 0x19  # Device identification handshake

# Captured ANNOUNCE payload template (349 bytes) - for BOOT sequence
# Values at: Battery=331-332, SOC=333-334, Bus=335-336
ANNOUNCE_TEMPLATE = bytes([
    0x44, 0x44, 0x44, 0x30, 0x43, 0x45, 0x51, 0x30, 0x33, 0x44, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x48, 0x55,
    0x45, 0x47, 0x42, 0x4c, 0x36, 0x30, 0x36, 0x33, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x03, 0x00, 0x00, 0x00, 0x2c, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0x35, 0x30, 0x32, 0x2e, 0x31, 0x30, 0x30,
    0x30, 0x32, 0x2e, 0x30, 0x37, 0x00, 0x00, 0x00, 0x35, 0x00, 0x00, 0x00, 0x06, 0x00, 0x01, 0x00,
    0x01, 0x00, 0x01, 0x00, 0x01, 0x48, 0x55, 0x45, 0x47, 0x42, 0x4c, 0x36, 0x30, 0x36, 0x33, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x1e, 0x02, 0x38, 0x02,
    0x38, 0x01, 0xf4, 0x00, 0x1e, 0x00, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x4e, 0x25, 0x00,
    0x00, 0x00, 0x2d, 0x00, 0x59, 0x07, 0xea, 0x00, 0x01, 0x00, 0x0a, 0x00, 0x0b, 0x00, 0x34, 0x00,
    0x0a, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x75, 0x30, 0x00, 0x00, 0x75, 0x30, 0x15, 0xe3, 0x00, 0x00, 0x00,
    0x96, 0x00, 0x00, 0x04, 0xb0, 0x02, 0x58, 0x01, 0xe0, 0x02, 0x58, 0x01, 0x2c, 0x04, 0xb0, 0x00,
    0x5a, 0x00, 0x86, 0x02, 0x58, 0x0b, 0xb8, 0x00, 0x04, 0x00, 0x1e, 0x01, 0xa4, 0x03, 0xb6, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x01, 0xff, 0xff, 0x00, 0x33, 0x00, 0x01, 0x00, 0x00, 0x00, 0x0c, 0x02, 0xf4, 0x00, 0x00, 0x00,
    0x00, 0x06, 0x4a, 0x00, 0x00, 0x00, 0x00, 0x00, 0x1e, 0x00, 0x00, 0x00, 0x00, 0x02, 0x94, 0x00,
    0x00, 0x03, 0x20, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x14, 0xa5, 0x00, 0x35, 0x08,
    0x30, 0x00, 0x00, 0x00, 0x00, 0x04, 0xb1, 0x17, 0x6f, 0x00, 0x00, 0x00, 0xd4,
])

# Captured DATA payload template (349 bytes) - for RUNNING phase (after boot)
# Values at: Timestamp=60-65, Battery=105-106, SOC=108, Bus=109-110
#
# NOTE: Hardcoded energy values in template (2026-01-10 analysis):
#   - Offset 173: Energy Today (0.7 kWh at capture time)
#   - Offset 177-178: Energy Total (1945.4 kWh at capture time)
#   These appear to be tracked SERVER-SIDE based on accumulated power data.
#   The portal displays correct values even though we don't update these offsets.
#   If energy tracking becomes inaccurate, consider reading Modbus energy registers
#   and updating these offsets dynamically.
#
DATA_TEMPLATE = bytes([
    0x44, 0x44, 0x44, 0x30, 0x43, 0x45, 0x51, 0x30, 0x33, 0x44, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x48, 0x55,
    0x45, 0x47, 0x42, 0x4c, 0x36, 0x30, 0x36, 0x33, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x1a, 0x01, 0x0a, 0x0c,
    0x02, 0x30, 0x03, 0x00, 0x00, 0x00, 0x2c, 0x00, 0x0c, 0x03, 0x12, 0x00, 0x00, 0x00, 0x00, 0x07,
    0x9e, 0x00, 0x00, 0x00, 0x00, 0x00, 0x24, 0x00, 0x00, 0x00, 0x00, 0x02, 0x62, 0x00, 0x00, 0x03,
    0x20, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x14, 0xd2, 0x00, 0x3c, 0x08, 0x40, 0x00,
    0x00, 0x00, 0x00, 0x04, 0xb2, 0x17, 0x70, 0x00, 0x00, 0x00, 0xcf, 0x00, 0xc1, 0x00, 0x1a, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xad, 0x00, 0xc5, 0x00, 0x06, 0x00, 0x0e, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x4e,
    0x25, 0x00, 0x2d, 0x00, 0x59, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x07, 0x00,
    0x00, 0x4b, 0xfe, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x1e, 0x00, 0x00, 0x00, 0x04, 0x00, 0x00, 0x1b, 0xf5, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0xff, 0xff, 0xfb, 0x3c, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x15, 0x00, 0x16, 0x00, 0x00, 0x00, 0x00, 0x00, 0x07, 0x00, 0x00, 0x1f, 0xce, 0x00, 0x00, 0x00,
    0x5a, 0x00, 0x86, 0x00, 0x24, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
])


def xor_encrypt(data):
    """XOR encrypt/decrypt data with 'Growatt' mask."""
    result = bytearray()
    for i, byte in enumerate(data):
        result.append(byte ^ XOR_MASK[i % len(XOR_MASK)])
    return bytes(result)


def calculate_crc16(data):
    """Calculate CRC-16/MODBUS."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc


class GrowattCloudClient:
    """
    Client for sending data to Growatt cloud servers.

    Based on captured packet analysis:
    - Protocol ID: 6 (encrypted)
    - Encryption: XOR with "Growatt"
    - Packet format: [tid:2][pid:2][len:2][uid:1][type:1][payload][crc:2]
    """

    def __init__(self):
        self.sock = None
        self.connected = False
        self.transaction_id = 1
        self.boot_complete = False  # Track if boot sequence is done
        self.data_tid = 2  # Separate TID counter for data packets

    def connect(self):
        """Connect to Growatt server."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(30)
            self.sock.connect((GROWATT_SERVER, GROWATT_PORT))
            self.connected = True
            print(f"[{datetime.now()}] Connected to {GROWATT_SERVER}:{GROWATT_PORT}")
            return True
        except Exception as e:
            print(f"[{datetime.now()}] Connection failed: {e}")
            self.connected = False
            return False

    def disconnect(self):
        """Close connection."""
        if self.sock:
            try:
                self.sock.close()
            except:
                pass
        self.connected = False

    def _get_tid(self):
        """Get next transaction ID."""
        tid = self.transaction_id
        self.transaction_id = (self.transaction_id + 1) % 65536
        return tid

    def _build_packet(self, msg_type, payload_data):
        """
        Build encrypted Growatt packet.

        Format: [tid:2][pid:2][len:2][uid:1][type:1][encrypted_payload][crc:2]

        Based on captured traffic:
        - tid: Transaction ID (incremented)
        - pid: Protocol ID (0x0006 = encrypted)
        - len: Length of everything after pid (uid + type + encrypted_payload + crc)
        - uid: Unit ID (0x01)
        - type: Message type
        - payload: XOR encrypted data
        - crc: CRC-16 MODBUS of header + encrypted_payload
        """
        # Encrypt payload
        encrypted = xor_encrypt(payload_data)

        # Length = uid(1) + type(1) + encrypted_payload (NOT including CRC!)
        length = 1 + 1 + len(encrypted)

        # Build header
        header = struct.pack('>HHH', self._get_tid(), PROTOCOL_ID, length)
        header += struct.pack('BB', UNIT_ID, msg_type)

        # Calculate CRC on header + encrypted payload
        crc = calculate_crc16(header + encrypted)

        # Build complete packet: header + encrypted + CRC
        packet = header + encrypted + struct.pack('>H', crc)

        return packet

    def _build_packet_with_tid(self, msg_type, payload_data, tid):
        """Build packet with specific transaction ID."""
        encrypted = xor_encrypt(payload_data)
        length = 1 + 1 + len(encrypted)
        header = struct.pack('>HHH', tid, PROTOCOL_ID, length)
        header += struct.pack('BB', UNIT_ID, msg_type)
        crc = calculate_crc16(header + encrypted)
        packet = header + encrypted + struct.pack('>H', crc)
        return packet

    def _recv_response(self, timeout=10):
        """Receive and parse server response."""
        self.sock.settimeout(timeout)
        try:
            response = self.sock.recv(1024)
            if response:
                print(f"[{datetime.now()}] Response ({len(response)} bytes): {response.hex()}")
                return response
        except socket.timeout:
            print(f"[{datetime.now()}] No response (timeout)")
        except Exception as e:
            print(f"[{datetime.now()}] Recv error: {e}")
        return None

    def send_ping(self):
        """
        Send PING/heartbeat packet.

        Based on captured traffic:
        - Type: 0x16
        - Payload: 30-byte datalogger serial (padded with nulls)
        """
        # Build payload: 30-byte serial
        payload = DATALOGGER_SERIAL.encode('ascii')[:30].ljust(30, b'\x00')

        packet = self._build_packet(MSG_TYPE_PING, payload)

        try:
            self.sock.sendall(packet)
            print(f"[{datetime.now()}] Sent PING ({len(packet)} bytes)")
            return True
        except Exception as e:
            print(f"[{datetime.now()}] Ping failed: {e}")
            self.connected = False
            return False

    def send_data(self, inverter_data):
        """
        Send inverter data packet using captured template.

        BOOT phase: Use ANNOUNCE (0x03) with ANNOUNCE_TEMPLATE
        RUN phase: Use DATA (0x04) with DATA_TEMPLATE (different offsets!)
        """
        now = datetime.now()

        # Extract values from inverter_data - DEBUG: print what we received
        bat_volt = inverter_data.get('bat_volt', 0)
        soc = inverter_data.get('bat_soc', 0)
        bus_volt = inverter_data.get('bus_volt', 0)
        status = inverter_data.get('status', 0)


        if not self.boot_complete:
            # BOOT: Use ANNOUNCE template (values at offsets 331-336)
            payload = bytearray(ANNOUNCE_TEMPLATE)


            # Update serials
            dl_bytes = DATALOGGER_SERIAL.encode('ascii')[:30].ljust(30, b'\x00')
            inv_bytes = INVERTER_SERIAL.encode('ascii')[:30].ljust(30, b'\x00')
            payload[0:30] = dl_bytes
            payload[30:60] = inv_bytes
            payload[117:127] = INVERTER_SERIAL.encode('ascii')[:10].ljust(10, b'\x00')

            # ANNOUNCE offsets - write dynamic values
            payload[66] = status & 0xFF
            struct.pack_into('>H', payload, 331, bat_volt)
            struct.pack_into('>H', payload, 333, soc)
            struct.pack_into('>H', payload, 335, bus_volt)


            msg_type = MSG_TYPE_ANNOUNCE
            packet = self._build_packet(msg_type, bytes(payload))
        else:
            # RUN: Use DATA template (values at different offsets!)
            payload = bytearray(DATA_TEMPLATE)

            # Update serials
            dl_bytes = DATALOGGER_SERIAL.encode('ascii')[:30].ljust(30, b'\x00')
            inv_bytes = INVERTER_SERIAL.encode('ascii')[:30].ljust(30, b'\x00')
            payload[0:30] = dl_bytes
            payload[30:60] = inv_bytes

            # DATA offsets - TIMESTAMP at 60-65
            payload[60] = now.year - 2000
            payload[61] = now.month
            payload[62] = now.day
            payload[63] = now.hour
            payload[64] = now.minute
            payload[65] = now.second

            # Status at offset 72 (display status)
            # Note: Byte 66 is a constant (0x03 = packet sub-type), NOT status
            # Verified: All 8 captured DATA packets have byte 66 = 3, byte 72 = status
            payload[72] = status & 0xFF

            # === ALL DYNAMIC VALUES FROM INVERTER ===
            # PV1 voltage at offset 73-74 (×10)
            vpv1 = inverter_data.get('vpv1', 0)
            struct.pack_into('>H', payload, 73, vpv1)

            # PV1 power at offset 79-80 (×10)
            ppv1 = inverter_data.get('ppv1', 0) & 0xFFFF  # Lower 16 bits
            struct.pack_into('>H', payload, 79, ppv1)

            # PV1 current at offset 85-86 (×10)
            buck1_curr = inverter_data.get('buck1_curr', 0)
            struct.pack_into('>H', payload, 85, buck1_curr)

            # Output power at offset 91-92 (×10)
            output_watt = inverter_data.get('output_watt', 0) & 0xFFFF
            struct.pack_into('>H', payload, 91, output_watt)

            # Output VA at offset 95-96 (×10)
            output_va = inverter_data.get('output_va', 0) & 0xFFFF
            struct.pack_into('>H', payload, 95, output_va)

            # Battery voltage at offset 105-106 (×100)
            struct.pack_into('>H', payload, 105, bat_volt)

            # SOC at offset 108 (%)
            payload[108] = soc & 0xFF

            # Bus voltage at offset 109-110 (×10)
            struct.pack_into('>H', payload, 109, bus_volt)

            # Output voltage at offset 115-116 (×10)
            output_volt = inverter_data.get('output_volt', 0)
            struct.pack_into('>H', payload, 115, output_volt)

            # Output frequency at offset 117-118 (×100)
            output_freq = inverter_data.get('output_freq', 0)
            struct.pack_into('>H', payload, 117, output_freq)

            # Load percentage at offset 126 (×10)
            load_percent = inverter_data.get('load_percent', 0)
            struct.pack_into('>H', payload, 125, load_percent)

            # Temperatures
            inv_temp = inverter_data.get('inv_temp', 0)
            dcdc_temp = inverter_data.get('dcdc_temp', 0)
            struct.pack_into('>H', payload, 136, inv_temp)
            struct.pack_into('>H', payload, 138, dcdc_temp)

            # Battery Power at offset 229 (32-bit signed, ×10)
            # Positive = Discharging, Negative = Charging
            bat_watt = inverter_data.get('bat_watt', 0)
            # Invert sign: Modbus positive=discharge, but protocol negative=charge
            # Actually from analysis: template has -1220 for charging 122W
            # So we need: charging = negative, discharging = positive (matches Modbus)
            struct.pack_into('>i', payload, 229, bat_watt)

            msg_type = MSG_TYPE_DATA
            # Use data TID counter
            self.data_tid += 1
            packet = self._build_packet_with_tid(msg_type, bytes(payload), self.data_tid)

        try:
            self.sock.sendall(packet)
            print(f"[{datetime.now()}] Sent DATA ({len(packet)} bytes)")
            return True
        except Exception as e:
            print(f"[{datetime.now()}] Data send failed: {e}")
            self.connected = False
            return False

    def _build_register_data(self, data):
        """
        Build register data section matching captured packet format.

        Based on analysis of captured decrypted payload at bytes 66+:
        The format appears to contain status, voltages, powers, etc.
        """
        reg = bytearray()

        # From captured data analysis, the register section contains:
        # Various 16-bit and 32-bit values representing inverter state

        # Status and basic info (matching captured pattern)
        reg.extend(struct.pack('>H', data.get('status', 0)))        # Status
        reg.extend(struct.pack('>H', 0))                             # Unknown
        reg.extend(struct.pack('>H', data.get('vpv1', 0)))          # PV1 Voltage (raw)
        reg.extend(struct.pack('>H', data.get('vpv2', 0)))          # PV2 Voltage (raw)

        # PV Power (32-bit values)
        reg.extend(struct.pack('>I', data.get('ppv1', 0)))          # PV1 Power
        reg.extend(struct.pack('>I', data.get('ppv2', 0)))          # PV2 Power

        # Buck currents
        reg.extend(struct.pack('>H', data.get('buck1_curr', 0)))
        reg.extend(struct.pack('>H', data.get('buck2_curr', 0)))

        # Output power
        reg.extend(struct.pack('>I', data.get('output_watt', 0)))
        reg.extend(struct.pack('>I', data.get('output_va', 0)))

        # Grid charge/discharge
        reg.extend(struct.pack('>I', data.get('grid_charge', 0)))
        reg.extend(struct.pack('>I', data.get('grid_discharge', 0)))

        # Battery
        reg.extend(struct.pack('>H', data.get('bat_volt', 0)))      # Battery voltage (raw, /100)
        reg.extend(struct.pack('>H', data.get('bat_soc', 0)))       # Battery SOC
        reg.extend(struct.pack('>H', data.get('bus_volt', 0)))      # Bus voltage

        # AC voltages and frequencies
        reg.extend(struct.pack('>H', data.get('grid_volt', 0)))     # Grid voltage
        reg.extend(struct.pack('>H', data.get('grid_freq', 0)))     # Grid frequency
        reg.extend(struct.pack('>H', data.get('output_volt', 0)))   # Output voltage
        reg.extend(struct.pack('>H', data.get('output_freq', 0)))   # Output frequency

        # Padding
        reg.extend(struct.pack('>H', 0))

        # Temperatures
        reg.extend(struct.pack('>H', data.get('inv_temp', 0)))      # Inverter temp
        reg.extend(struct.pack('>H', data.get('dcdc_temp', 0)))     # DC-DC temp
        reg.extend(struct.pack('>H', data.get('load_percent', 0)))  # Load percent

        # More padding and additional values
        reg.extend(bytes(20))  # Padding

        reg.extend(struct.pack('>H', data.get('buck1_temp', 0)))    # Buck1 temp
        reg.extend(struct.pack('>H', data.get('buck2_temp', 0)))    # Buck2 temp
        reg.extend(struct.pack('>H', data.get('output_curr', 0)))   # Output current
        reg.extend(struct.pack('>H', data.get('inv_curr', 0)))      # Inverter current

        # AC input power
        reg.extend(struct.pack('>I', data.get('ac_in_watt', 0)))
        reg.extend(struct.pack('>I', data.get('ac_in_va', 0)))

        # Battery power (signed 32-bit)
        bat_power = data.get('bat_watt', 0)
        if bat_power < 0:
            bat_power = bat_power + 0x100000000  # Convert to unsigned
        reg.extend(struct.pack('>I', bat_power))

        # Fill remaining space with zeros to match captured packet
        while len(reg) < 283:  # 349 - 66 = 283 bytes for register section
            reg.append(0x00)

        return bytes(reg)

    def respond_to_identify(self, request_data):
        """
        Respond to server IDENTIFY request.

        From captured traffic:
        - Server sends: serial + [00 04 00 15] (request type 4, subtype 21)
        - Dongle responds: serial + [00 04 00 01 35] (response with config)
        """
        # Build response payload
        payload = bytearray()
        payload.extend(DATALOGGER_SERIAL.encode('ascii')[:30].ljust(30, b'\x00'))

        # Response config bytes (from captured dongle)
        # Format: [00 04 00 01 35] where 35 (0x35 = 53) might be firmware version or device type
        payload.extend(bytes([0x00, 0x04, 0x00, 0x01, 0x35]))

        packet = self._build_packet(MSG_TYPE_IDENTIFY, bytes(payload))

        try:
            self.sock.sendall(packet)
            print(f"[{datetime.now()}] Sent IDENTIFY response (type 4)")
            return True
        except Exception as e:
            print(f"[{datetime.now()}] IDENTIFY response failed: {e}")
            return False

    def send_config_packets(self):
        """
        Send additional config packets that the dongle sends after ANNOUNCE.

        From captured traffic, the dongle sends these IDENTIFY packets:
        - Type 5: [0, 5, 0, 1, 49]
        - Type 6: [0, 6, 0, 2, 51, 50]
        - Type 7: [0, 7, 0, 1, 187]
        - Type 9: [0, 9, 0, 4, ...]
        """
        configs = [
            bytes([0x00, 0x05, 0x00, 0x01, 0x31]),  # Type 5
            bytes([0x00, 0x06, 0x00, 0x02, 0x33, 0x32]),  # Type 6 - "32"
            bytes([0x00, 0x07, 0x00, 0x01, 0xBB]),  # Type 7
        ]

        for i, config_data in enumerate(configs):
            payload = bytearray()
            payload.extend(DATALOGGER_SERIAL.encode('ascii')[:30].ljust(30, b'\x00'))
            payload.extend(config_data)

            packet = self._build_packet(MSG_TYPE_IDENTIFY, bytes(payload))

            try:
                self.sock.sendall(packet)
                print(f"[{datetime.now()}] Sent config packet (type {config_data[1]})")
                time.sleep(0.1)  # Small delay between packets
            except Exception as e:
                print(f"[{datetime.now()}] Config packet failed: {e}")
                return False

        return True

    def wait_for_response(self):
        """Wait for and handle server response."""
        response = self._recv_response(timeout=5)
        if response and len(response) >= 8:
            # Parse response header
            tid = struct.unpack('>H', response[0:2])[0]
            pid = struct.unpack('>H', response[2:4])[0]
            length = struct.unpack('>H', response[4:6])[0]
            uid = response[6]
            msg_type = response[7]

            print(f"[{datetime.now()}] Response: tid={tid}, type=0x{msg_type:02x}")

            # Handle IDENTIFY request from server
            if msg_type == MSG_TYPE_IDENTIFY:
                print(f"[{datetime.now()}] Server requesting IDENTIFY - responding...")
                self.respond_to_identify(response[8:])
                # Wait for next response (should be PING ack)
                return self.wait_for_response()

            return msg_type
        return None


def should_upload(snapshot):
    """Decide whether a gateway snapshot is safe to forward to the cloud.

    Returns False for anything that isn't a fresh, real Modbus reading --
    this is the actual fix for the original incident, where a snapshot
    that was fabricated (source=test_data) or stale still got sent to
    server.growatt.com looking exactly like live data.
    """
    if snapshot is None:
        return False
    if snapshot.get('source') != 'modbus':
        return False
    if snapshot.get('stale'):
        return False
    return True


def fetch_latest_reading():
    """Fetch the latest inverter reading from the local gateway service.

    Returns the gateway's /latest JSON (raw_registers, reading, timestamp,
    age_seconds, stale, source), or None if the gateway is unreachable.
    """
    try:
        with urllib.request.urlopen(GATEWAY_URL, timeout=5) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 503:
            return None  # gateway is up but has no reading yet
        print(f"[{datetime.now()}] Gateway returned HTTP {e.code}")
        return None
    except Exception as e:
        print(f"[{datetime.now()}] Gateway fetch failed: {e}")
        return None


def main():
    """Main loop - fetch inverter data from the gateway and send to cloud."""

    if not DATALOGGER_SERIAL:
        print("Error: GROWATT_DATALOGGER_SERIAL not set in .env")
        return

    print("=" * 60)
    print("Growatt Cloud Upload Service")
    print("=" * 60)
    print(f"Datalogger: {DATALOGGER_SERIAL}")
    print(f"Inverter:   {INVERTER_SERIAL}")
    print(f"Server:     {GROWATT_SERVER}:{GROWATT_PORT}")
    print(f"Gateway:    {GATEWAY_URL}")
    print("=" * 60)

    cloud = GrowattCloudClient()

    last_data_time = 0
    last_ping_time = 0

    try:
        while True:
            now = time.time()

            # Ensure cloud connection
            if not cloud.connected:
                if cloud.connect():
                    # Send initial ping
                    cloud.send_ping()
                    cloud.wait_for_response()
                    last_ping_time = now
                else:
                    print("Retrying connection in 30 seconds...")
                    time.sleep(30)
                    continue

            # Send ping every 3 minutes
            if now - last_ping_time >= PING_INTERVAL:
                cloud.send_ping()
                cloud.wait_for_response()
                last_ping_time = now

            # Send data every 5 minutes
            if now - last_data_time >= DATA_INTERVAL:
                snapshot = fetch_latest_reading()

                if snapshot is None:
                    # Gateway unreachable or has no reading at all yet -- retry
                    # sooner rather than waiting a full DATA_INTERVAL.
                    print(f"[{datetime.now()}] No reading from gateway, will retry shortly")
                elif not should_upload(snapshot):
                    # Never forward fabricated or stale-but-looks-current data
                    # to the cloud dashboard -- this was the root cause of the
                    # original mismatch (see docs/GATEWAY.md).
                    print(f"[{datetime.now()}] Gateway reading is source="
                          f"{snapshot.get('source')} stale={snapshot.get('stale')} "
                          f"age={snapshot.get('age_seconds')}s -- skipping cloud upload")
                    last_data_time = now
                else:
                    try:
                        data = snapshot['raw_registers']
                        cloud.send_data(data)
                        resp = cloud.wait_for_response()

                        # Send additional config packets after ANNOUNCE ACK (boot phase only)
                        if resp == MSG_TYPE_ANNOUNCE and not cloud.boot_complete:
                            cloud.send_config_packets()
                            cloud.boot_complete = True  # Mark boot as complete
                            print(f"[{datetime.now()}] Boot sequence complete, switching to DATA packets")

                        # Handle DATA ACK (running phase)
                        if resp == MSG_TYPE_DATA:
                            print(f"[{datetime.now()}] DATA acknowledged")

                        last_data_time = now

                        # Print summary (scaled values come straight from the gateway)
                        r = snapshot['reading']
                        pkt_type = "ANNOUNCE" if not cloud.boot_complete else "DATA"
                        print(f"  [{pkt_type}] Status: {r['status']}, "
                              f"PV: {r['vpv1_v']}V/{r['ppv1_w']}W, "
                              f"Bat: {r['bat_volt_v']}V @ {r['bat_soc_pct']}%, "
                              f"Out: {r['output_w']}W")
                    except Exception as e:
                        print(f"Error sending data: {e}")
                        import traceback
                        traceback.print_exc()

            time.sleep(10)

    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        cloud.disconnect()


if __name__ == "__main__":
    main()
