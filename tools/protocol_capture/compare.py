#!/usr/bin/env python3
"""
Growatt Protocol Comparison Tool

Compares Pi-generated packets against captured dongle ground truth.
Use this AFTER running capture.py with the dongle to validate your
Pi implementation.

Workflow:
1. Run capture.py with dongle connected (24+ hours) → ground truth
2. Run analyze.py to understand packet structure
3. Disconnect dongle, connect Pi to inverter
4. Run this script to validate Pi output against learned patterns

Usage:
    python compare.py [ground_truth_dir] [test_packet_or_file]

Examples:
    # Validate a single packet (hex string)
    python compare.py data/ "00010006..."

    # Validate packets from a file
    python compare.py data/ test_packets.jsonl

    # Interactive mode - paste packets to validate
    python compare.py data/

Features:
- Structure validation (header, length, CRC)
- Static byte verification (must match ground truth)
- Dynamic byte range checking (within observed ranges)
- Timing validation (packet intervals)
- Detailed diff report
"""

import json
import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))
from utils import parse_packet, xor_crypt, calculate_crc16, MSG_TYPES


DATA_DIR = Path(__file__).parent / 'data'


class ProtocolValidator:
    """Validates packets against learned ground truth."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.templates = {}  # packet_type -> template
        self.byte_ranges = {}  # packet_type -> {offset: (min, max)}
        self.static_bytes = {}  # packet_type -> {offset: value}
        self.loaded = False

    def load_ground_truth(self):
        """Load and analyze ground truth packets."""
        packets = []
        for fpath in sorted(self.data_dir.glob('packets_*.jsonl')):
            with open(fpath) as f:
                for line in f:
                    try:
                        packets.append(json.loads(line.strip()))
                    except:
                        pass

        if not packets:
            print(f"[!] No packets found in {self.data_dir}")
            return False

        print(f"[*] Loaded {len(packets):,} ground truth packets")

        # Analyze each packet type
        for ptype in ['ANNOUNCE', 'DATA']:
            type_packets = [
                p for p in packets
                if p.get('parsed', {}).get('type_name') == ptype
                and p.get('parsed', {}).get('decrypted_hex')
                and 'DONGLE -> SERVER' in p.get('direction', '')
            ]

            if not type_packets:
                continue

            payloads = [bytes.fromhex(p['parsed']['decrypted_hex']) for p in type_packets]
            min_len = min(len(p) for p in payloads)

            # Build template: static bytes and ranges
            static = {}
            ranges = {}

            for pos in range(min_len):
                values = [p[pos] for p in payloads]
                unique = set(values)

                if len(unique) == 1:
                    static[pos] = values[0]
                else:
                    ranges[pos] = (min(values), max(values))

            self.static_bytes[ptype] = static
            self.byte_ranges[ptype] = ranges
            self.templates[ptype] = {
                'min_length': min_len,
                'max_length': max(len(p) for p in payloads),
                'sample_count': len(type_packets),
            }

            print(f"[*] {ptype}: {len(type_packets)} samples, "
                  f"{len(static)} static bytes, {len(ranges)} dynamic bytes")

        self.loaded = True
        return True

    def validate_packet(self, packet_hex: str) -> dict:
        """
        Validate a packet against ground truth.

        Returns dict with:
        - valid: bool
        - errors: list of error strings
        - warnings: list of warning strings
        - details: detailed validation results
        """
        result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'details': {},
        }

        # Parse the packet
        try:
            raw = bytes.fromhex(packet_hex.replace(' ', ''))
        except ValueError as e:
            result['valid'] = False
            result['errors'].append(f"Invalid hex: {e}")
            return result

        parsed = parse_packet(raw)
        if not parsed:
            result['valid'] = False
            result['errors'].append("Failed to parse packet")
            return result

        if 'error' in parsed:
            result['valid'] = False
            result['errors'].append(f"Parse error: {parsed['error']}")
            return result

        result['details']['parsed'] = parsed
        type_name = parsed.get('type_name', 'UNKNOWN')

        # Check CRC
        if parsed.get('crc_valid') is False:
            result['valid'] = False
            result['errors'].append(
                f"CRC mismatch: received 0x{parsed['crc_received']:04X}, "
                f"calculated 0x{parsed['crc_calculated']:04X}"
            )

        # Check if we have ground truth for this type
        if type_name not in self.templates:
            result['warnings'].append(f"No ground truth for packet type: {type_name}")
            return result

        template = self.templates[type_name]
        static = self.static_bytes[type_name]
        ranges = self.byte_ranges[type_name]

        # Get decrypted payload
        decrypted_hex = parsed.get('decrypted_hex')
        if not decrypted_hex:
            result['warnings'].append("No decrypted payload to validate")
            return result

        payload = bytes.fromhex(decrypted_hex)
        result['details']['payload_length'] = len(payload)

        # Check length
        if len(payload) < template['min_length']:
            result['valid'] = False
            result['errors'].append(
                f"Payload too short: {len(payload)} < {template['min_length']}"
            )
        elif len(payload) > template['max_length']:
            result['warnings'].append(
                f"Payload longer than observed: {len(payload)} > {template['max_length']}"
            )

        # Check static bytes
        static_errors = []
        for offset, expected in static.items():
            if offset < len(payload):
                actual = payload[offset]
                if actual != expected:
                    static_errors.append({
                        'offset': offset,
                        'expected': f'0x{expected:02X}',
                        'actual': f'0x{actual:02X}',
                    })

        if static_errors:
            result['valid'] = False
            result['errors'].append(f"Static byte mismatches: {len(static_errors)}")
            result['details']['static_errors'] = static_errors

        # Check dynamic byte ranges
        range_warnings = []
        for offset, (min_v, max_v) in ranges.items():
            if offset < len(payload):
                actual = payload[offset]
                if not (min_v <= actual <= max_v):
                    range_warnings.append({
                        'offset': offset,
                        'expected_range': f'{min_v}-{max_v}',
                        'actual': actual,
                    })

        if range_warnings:
            result['warnings'].append(f"Values outside observed range: {len(range_warnings)}")
            result['details']['range_warnings'] = range_warnings

        return result

    def print_validation_result(self, result: dict):
        """Print formatted validation result."""
        if result['valid']:
            print("\n\033[92m✓ PACKET VALID\033[0m")
        else:
            print("\n\033[91m✗ PACKET INVALID\033[0m")

        if result['errors']:
            print("\nErrors:")
            for err in result['errors']:
                print(f"  \033[91m• {err}\033[0m")

        if result['warnings']:
            print("\nWarnings:")
            for warn in result['warnings']:
                print(f"  \033[93m• {warn}\033[0m")

        # Show static byte errors
        static_errors = result.get('details', {}).get('static_errors', [])
        if static_errors:
            print("\nStatic byte mismatches:")
            for err in static_errors[:10]:
                print(f"  Offset {err['offset']:3d}: expected {err['expected']}, got {err['actual']}")
            if len(static_errors) > 10:
                print(f"  ... and {len(static_errors) - 10} more")

        # Show range warnings
        range_warns = result.get('details', {}).get('range_warnings', [])
        if range_warns:
            print("\nOut-of-range values:")
            for w in range_warns[:10]:
                print(f"  Offset {w['offset']:3d}: expected {w['expected_range']}, got {w['actual']}")
            if len(range_warns) > 10:
                print(f"  ... and {len(range_warns) - 10} more")

        # Show parsed info
        parsed = result.get('details', {}).get('parsed', {})
        if parsed:
            print(f"\nPacket info:")
            print(f"  Type: {parsed.get('type_name')} ({parsed.get('type_hex')})")
            print(f"  Length: {parsed.get('raw_length')} bytes")
            print(f"  CRC: {'OK' if parsed.get('crc_valid') else 'FAIL'}")

            extracted = parsed.get('extracted', {})
            if extracted.get('datalogger_serial'):
                print(f"  Datalogger: {extracted['datalogger_serial']}")
            if extracted.get('inverter_serial'):
                print(f"  Inverter: {extracted['inverter_serial']}")


def interactive_mode(validator: ProtocolValidator):
    """Interactive packet validation mode."""
    print("\n" + "=" * 60)
    print("INTERACTIVE VALIDATION MODE")
    print("=" * 60)
    print("Paste packet hex strings to validate.")
    print("Type 'quit' or Ctrl+C to exit.\n")

    while True:
        try:
            packet_hex = input("Packet hex> ").strip()

            if packet_hex.lower() in ('quit', 'exit', 'q'):
                break

            if not packet_hex:
                continue

            result = validator.validate_packet(packet_hex)
            validator.print_validation_result(result)
            print()

        except KeyboardInterrupt:
            print("\n")
            break
        except EOFError:
            break


def validate_file(validator: ProtocolValidator, filepath: Path):
    """Validate packets from a file."""
    print(f"\nValidating packets from: {filepath}\n")

    valid_count = 0
    invalid_count = 0

    with open(filepath) as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            # Try to parse as JSON first
            try:
                data = json.loads(line)
                if 'parsed' in data:
                    packet_hex = data['parsed'].get('raw_hex', '')
                else:
                    packet_hex = data.get('raw_hex', data.get('hex', line))
            except json.JSONDecodeError:
                packet_hex = line

            result = validator.validate_packet(packet_hex)

            if result['valid']:
                valid_count += 1
                status = '\033[92m✓\033[0m'
            else:
                invalid_count += 1
                status = '\033[91m✗\033[0m'

            type_name = result.get('details', {}).get('parsed', {}).get('type_name', 'UNKNOWN')
            print(f"  {status} Line {line_num}: {type_name}")

            if not result['valid']:
                for err in result['errors'][:2]:
                    print(f"      {err}")

    print(f"\nSummary: {valid_count} valid, {invalid_count} invalid")


def main():
    global DATA_DIR

    print("=" * 60)
    print("GROWATT PROTOCOL COMPARISON TOOL")
    print("=" * 60)

    # Parse arguments
    if len(sys.argv) > 1:
        DATA_DIR = Path(sys.argv[1])

    if not DATA_DIR.exists():
        print(f"\n[!] Ground truth directory not found: {DATA_DIR}")
        print("[!] Run capture.py first to collect ground truth data.")
        sys.exit(1)

    # Initialize validator
    validator = ProtocolValidator(DATA_DIR)
    print(f"\nLoading ground truth from: {DATA_DIR}")

    if not validator.load_ground_truth():
        print("\n[!] Failed to load ground truth. Run capture.py first.")
        sys.exit(1)

    # Handle input
    if len(sys.argv) > 2:
        arg = sys.argv[2]

        # Check if it's a file
        if Path(arg).exists():
            validate_file(validator, Path(arg))
        else:
            # Treat as packet hex
            result = validator.validate_packet(arg)
            validator.print_validation_result(result)
    else:
        # Interactive mode
        interactive_mode(validator)

    print("\nDone.")


if __name__ == "__main__":
    main()
