"""
Shared utilities for Growatt protocol capture and analysis.

Contains:
- XOR encryption/decryption
- CRC-16/MODBUS calculation
- Packet parsing
- Known protocol constants
"""

# XOR mask for encryption/decryption
XOR_MASK = b'Growatt'

# Known message types
MSG_TYPES = {
    0x03: 'ANNOUNCE',
    0x04: 'DATA',
    0x13: 'ACK_ANNOUNCE',
    0x14: 'ACK_DATA',
    0x16: 'PING',
    0x17: 'PONG',
    0x18: 'CONFIG',
    0x19: 'IDENTIFY',
    0x50: 'BUFFERED_DATA',
}

# Server response types (expected responses)
EXPECTED_SERVER_RESPONSES = {0x13, 0x14, 0x17}

# Server command types (active commands from server)
SERVER_COMMANDS = {0x18, 0x19}

# Protocol IDs that use XOR encryption
ENCRYPTED_PROTOCOLS = {5, 6}


def xor_crypt(data: bytes) -> bytes:
    """XOR encrypt/decrypt data with 'Growatt' mask (symmetric operation)."""
    result = bytearray()
    for i, byte in enumerate(data):
        result.append(byte ^ XOR_MASK[i % len(XOR_MASK)])
    return bytes(result)


def calculate_crc16(data: bytes) -> int:
    """Calculate CRC-16/MODBUS checksum."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc


def parse_packet(data: bytes) -> dict:
    """
    Parse a Growatt protocol packet.

    Packet structure:
    [TID:2][PID:2][Length:2][UID:1][Type:1][Payload:variable][CRC:2]

    Returns dict with all parsed fields or None if invalid.
    """
    if len(data) < 8:
        return None

    try:
        # Parse header
        tid = int.from_bytes(data[0:2], 'big')
        pid = int.from_bytes(data[2:4], 'big')
        length = int.from_bytes(data[4:6], 'big')
        uid = data[6]
        msg_type = data[7]

        # Extract payload and CRC
        payload = data[8:]
        payload_without_crc = payload[:-2] if len(payload) >= 2 else payload

        crc_received = None
        crc_calculated = None
        crc_valid = None

        if len(payload) >= 2:
            crc_received = int.from_bytes(payload[-2:], 'little')
            crc_calculated = calculate_crc16(data[:-2])
            crc_valid = crc_received == crc_calculated

        # Decrypt payload if encrypted protocol
        decrypted = None
        if pid in ENCRYPTED_PROTOCOLS and len(payload_without_crc) > 0:
            decrypted = xor_crypt(payload_without_crc)

        # Extract common fields from decrypted payload
        extracted = {}
        if decrypted and len(decrypted) >= 60:
            # Serials (common to most packet types)
            extracted['datalogger_serial'] = decrypted[0:30].rstrip(b'\x00').decode('ascii', errors='replace')
            extracted['inverter_serial'] = decrypted[30:60].rstrip(b'\x00').decode('ascii', errors='replace')

            # Timestamp if present (bytes 60-65)
            if len(decrypted) >= 66:
                try:
                    year = 2000 + decrypted[60]
                    month = decrypted[61]
                    day = decrypted[62]
                    hour = decrypted[63]
                    minute = decrypted[64]
                    second = decrypted[65]
                    if 1 <= month <= 12 and 1 <= day <= 31 and 0 <= hour <= 23:
                        extracted['packet_timestamp'] = f"{year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"
                except (IndexError, ValueError):
                    pass

        type_name = MSG_TYPES.get(msg_type, f'UNKNOWN_0x{msg_type:02X}')

        return {
            'tid': tid,
            'pid': pid,
            'pid_hex': f'0x{pid:04X}',
            'length': length,
            'uid': uid,
            'type': msg_type,
            'type_hex': f'0x{msg_type:02X}',
            'type_name': type_name,
            'payload_length': len(payload),
            'payload_hex': payload.hex(),
            'payload_without_crc_hex': payload_without_crc.hex() if payload_without_crc else '',
            'crc_received': crc_received,
            'crc_calculated': crc_calculated,
            'crc_valid': crc_valid,
            'decrypted_hex': decrypted.hex() if decrypted else None,
            'decrypted_length': len(decrypted) if decrypted else 0,
            'extracted': extracted,
            'raw_hex': data.hex(),
            'raw_length': len(data),
        }
    except Exception as e:
        return {
            'error': str(e),
            'raw_hex': data.hex(),
            'raw_length': len(data),
        }


def find_growatt_payload(raw_data: bytes, start_offset: int = 40) -> bytes:
    """
    Find Growatt protocol payload within raw packet data.

    Searches for valid protocol ID (5 or 6) after typical ethernet/IP/TCP headers.
    Returns the Growatt payload or None if not found.
    """
    for offset in range(start_offset, min(len(raw_data) - 8, 100)):
        if len(raw_data) > offset + 6:
            pid = int.from_bytes(raw_data[offset+2:offset+4], 'big')
            if pid in ENCRYPTED_PROTOCOLS:
                pkt_len = int.from_bytes(raw_data[offset+4:offset+6], 'big')
                if 4 < pkt_len < 1000:  # Reasonable packet length
                    return raw_data[offset:]
    return None


def find_byte_differences(old_hex: str, new_hex: str) -> list:
    """
    Find which byte positions differ between two hex strings.

    Returns list of diffs with offset, old value, new value.
    """
    if not old_hex or not new_hex:
        return []

    differences = []
    old_bytes = bytes.fromhex(old_hex)
    new_bytes = bytes.fromhex(new_hex)

    min_len = min(len(old_bytes), len(new_bytes))
    for i in range(min_len):
        if old_bytes[i] != new_bytes[i]:
            differences.append({
                'offset': i,
                'old': f'0x{old_bytes[i]:02X}',
                'new': f'0x{new_bytes[i]:02X}',
                'old_dec': old_bytes[i],
                'new_dec': new_bytes[i],
            })

    if len(old_bytes) != len(new_bytes):
        differences.append({
            'length_change': f'{len(old_bytes)} -> {len(new_bytes)}'
        })

    return differences


def format_packet_summary(parsed: dict, direction: str = '') -> str:
    """Format a one-line summary of a parsed packet."""
    type_name = parsed.get('type_name', 'UNKNOWN')
    length = parsed.get('raw_length', 0)
    crc_status = '[CRC OK]' if parsed.get('crc_valid') else '[CRC FAIL]' if parsed.get('crc_valid') is False else ''

    extra = ''
    extracted = parsed.get('extracted', {})
    if extracted.get('packet_timestamp'):
        extra = f" ts={extracted['packet_timestamp']}"

    arrow = ''
    if 'SERVER' in direction and 'DONGLE' in direction:
        arrow = '← ' if 'SERVER -> DONGLE' in direction else '→ '

    return f"{arrow}{type_name:12} {length:4}B {crc_status}{extra}"
