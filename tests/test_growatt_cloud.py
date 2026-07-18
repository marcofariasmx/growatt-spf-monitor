"""Tests for growatt_cloud.py: the cloud protocol packet building and the
should_upload() safety check that decides what's allowed to reach
server.growatt.com.
"""
import struct

from growatt_cloud import (
    MSG_TYPE_PING,
    PROTOCOL_ID,
    UNIT_ID,
    GrowattCloudClient,
    calculate_crc16,
    should_upload,
    xor_encrypt,
)


def test_xor_encrypt_is_involutive():
    original = b"hello growatt world, 1234567890"
    encrypted = xor_encrypt(original)

    assert encrypted != original
    assert xor_encrypt(encrypted) == original


def test_calculate_crc16_is_deterministic_and_sensitive_to_input():
    data = b"\x00\x01\x00\x06\x00\x20\x01\x16"

    assert calculate_crc16(data) == calculate_crc16(data)
    assert calculate_crc16(data + b"\x00") != calculate_crc16(data)


def test_build_packet_header_fields():
    client = GrowattCloudClient()
    payload = b"PAYLOAD-DATA-1234567890"
    packet = client._build_packet(MSG_TYPE_PING, payload)

    tid, pid, length, uid, msg_type = struct.unpack('>HHHBB', packet[:8])

    assert pid == PROTOCOL_ID
    assert uid == UNIT_ID
    assert msg_type == MSG_TYPE_PING
    # length = uid(1) + type(1) + encrypted_payload, per the protocol docstring
    assert length == 1 + 1 + len(payload)


def test_build_packet_payload_roundtrips_and_crc_matches():
    client = GrowattCloudClient()
    payload = b"PAYLOAD-DATA-1234567890"
    packet = client._build_packet(MSG_TYPE_PING, payload)

    encrypted_payload = packet[8:8 + len(payload)]
    assert xor_encrypt(encrypted_payload) == payload

    crc_bytes = packet[8 + len(payload):]
    expected_crc = calculate_crc16(packet[:8 + len(payload)])
    assert struct.unpack('>H', crc_bytes)[0] == expected_crc


def test_build_packet_increments_transaction_id():
    client = GrowattCloudClient()
    first_tid = struct.unpack('>H', client._build_packet(MSG_TYPE_PING, b'x')[:2])[0]
    second_tid = struct.unpack('>H', client._build_packet(MSG_TYPE_PING, b'x')[:2])[0]

    assert second_tid == first_tid + 1


def test_should_upload_rejects_missing_snapshot():
    assert should_upload(None) is False


def test_should_upload_rejects_test_data_source():
    """This is the actual root-cause fix: a fabricated snapshot must never
    be forwarded to the cloud as if it were live."""
    assert should_upload({'source': 'test_data', 'stale': False}) is False


def test_should_upload_rejects_stale_reading():
    assert should_upload({'source': 'modbus', 'stale': True}) is False


def test_should_upload_accepts_fresh_modbus_reading():
    assert should_upload({'source': 'modbus', 'stale': False}) is True
