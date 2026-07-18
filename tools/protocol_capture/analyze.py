#!/usr/bin/env python3
"""
Growatt Protocol Capture Analysis

Analyzes captured packets to understand protocol structure:
- Byte-level analysis (static vs dynamic positions)
- Timing patterns between packet types
- Value correlations (16/32-bit values, scaling factors)
- Diff patterns (what changes between packets)
- Unknown packet type documentation

Usage:
    python analyze.py [data_directory]
    python analyze.py                    # Uses ./data/
    python analyze.py /path/to/capture   # Custom path

Output:
    Prints analysis to stdout
    Saves detailed report to data/analysis_YYYYMMDD_HHMMSS.txt
"""

import json
import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# Default data directory
DATA_DIR = Path(__file__).parent / 'data'


def load_packets(data_dir: Path) -> list:
    """Load all packets from JSONL files."""
    packets = []
    jsonl_files = sorted(data_dir.glob('packets_*.jsonl'))

    if not jsonl_files:
        print(f"No packet files found in {data_dir}")
        return packets

    print(f"Loading from {len(jsonl_files)} files...")

    for fpath in jsonl_files:
        with open(fpath) as f:
            for line_num, line in enumerate(f, 1):
                try:
                    packets.append(json.loads(line.strip()))
                except json.JSONDecodeError:
                    pass

    print(f"Loaded {len(packets):,} packets\n")
    return packets


def analyze_byte_positions(packets: list, packet_type: str) -> dict:
    """Analyze which byte positions are static vs dynamic."""
    type_packets = [
        p for p in packets
        if p.get('parsed', {}).get('type_name') == packet_type
        and p.get('parsed', {}).get('decrypted_hex')
    ]

    if not type_packets:
        return None

    print(f"\n{'='*70}")
    print(f"BYTE POSITION ANALYSIS: {packet_type}")
    print(f"{'='*70}")
    print(f"Samples: {len(type_packets)}")

    payloads = [bytes.fromhex(p['parsed']['decrypted_hex']) for p in type_packets]
    min_len = min(len(p) for p in payloads)
    max_len = max(len(p) for p in payloads)

    print(f"Payload length: {min_len}-{max_len} bytes")

    # Analyze each byte position
    analysis = []
    for pos in range(min_len):
        values = [p[pos] for p in payloads]
        unique = set(values)

        analysis.append({
            'position': pos,
            'unique_count': len(unique),
            'min': min(values),
            'max': max(values),
            'is_static': len(unique) == 1,
            'static_value': values[0] if len(unique) == 1 else None,
            'samples': list(unique)[:5],
        })

    static = [a for a in analysis if a['is_static']]
    dynamic = [a for a in analysis if not a['is_static']]

    print(f"\nStatic bytes: {len(static)} ({100*len(static)/len(analysis):.1f}%)")
    print(f"Dynamic bytes: {len(dynamic)} ({100*len(dynamic)/len(analysis):.1f}%)")

    # Find contiguous static regions
    print("\n--- Static Regions ---")
    i = 0
    while i < len(analysis):
        if analysis[i]['is_static']:
            start = i
            values = []
            while i < len(analysis) and analysis[i]['is_static']:
                values.append(analysis[i]['static_value'])
                i += 1
            end = i - 1

            # Format output
            hex_str = ' '.join(f'{v:02X}' for v in values[:16])
            if len(values) > 16:
                hex_str += f' ... (+{len(values)-16})'

            # Check for ASCII
            ascii_str = ''.join(chr(v) if 32 <= v <= 126 else '.' for v in values)
            has_ascii = len(ascii_str.replace('.', '')) > 2

            print(f"  [{start:3d}-{end:3d}] ({end-start+1:3d}B): {hex_str}")
            if has_ascii:
                print(f"           ASCII: '{ascii_str[:40]}'")
        else:
            i += 1

    # Find contiguous dynamic regions
    print("\n--- Dynamic Regions (values that change) ---")
    i = 0
    while i < len(analysis):
        if not analysis[i]['is_static']:
            start = i
            region = []
            while i < len(analysis) and not analysis[i]['is_static']:
                region.append(analysis[i])
                i += 1
            end = i - 1

            print(f"  [{start:3d}-{end:3d}] ({end-start+1:3d}B):")
            for b in region[:8]:
                print(f"    @{b['position']:3d}: range {b['min']:3d}-{b['max']:3d}, {b['unique_count']} unique")
            if len(region) > 8:
                print(f"    ... +{len(region)-8} more positions")
        else:
            i += 1

    return {'static': static, 'dynamic': dynamic, 'analysis': analysis}


def analyze_timing(packets: list):
    """Analyze timing patterns between packets."""
    print(f"\n{'='*70}")
    print("TIMING ANALYSIS")
    print(f"{'='*70}")

    # Group by type (outgoing only)
    by_type = defaultdict(list)
    for p in packets:
        direction = p.get('direction', '')
        if 'DONGLE -> SERVER' not in direction:
            continue

        type_name = p.get('parsed', {}).get('type_name', 'UNKNOWN')
        ts_str = p.get('capture_timestamp') or p.get('timestamp')

        if ts_str:
            try:
                # Handle different timestamp formats
                if 'T' in ts_str:
                    ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                else:
                    ts = datetime.strptime(ts_str.split('.')[0], '%Y-%m-%d %H:%M:%S')
                by_type[type_name].append(ts)
            except:
                pass

    for type_name, timestamps in sorted(by_type.items()):
        if len(timestamps) < 2:
            continue

        timestamps.sort()
        intervals = [(timestamps[i] - timestamps[i-1]).total_seconds()
                     for i in range(1, len(timestamps))]

        if not intervals:
            continue

        avg = sum(intervals) / len(intervals)
        print(f"\n{type_name}:")
        print(f"  Count: {len(timestamps)}")
        print(f"  Avg interval: {avg:.1f}s ({avg/60:.1f}min)")
        print(f"  Range: {min(intervals):.1f}s - {max(intervals):.1f}s")

        # Check periodicity
        if avg > 0:
            variance = sum((i - avg)**2 for i in intervals) / len(intervals)
            std = variance ** 0.5
            cv = std / avg

            if cv < 0.1:
                print(f"  → Highly periodic (~{avg:.0f}s)")
            elif cv < 0.3:
                print(f"  → Somewhat periodic")
            else:
                print(f"  → Irregular")


def analyze_value_candidates(packets: list, packet_type: str):
    """Look for potential 16/32-bit values in payload."""
    type_packets = [
        p for p in packets
        if p.get('parsed', {}).get('type_name') == packet_type
        and p.get('parsed', {}).get('decrypted_hex')
    ]

    if len(type_packets) < 5:
        return

    print(f"\n{'='*70}")
    print(f"VALUE CANDIDATES: {packet_type}")
    print(f"{'='*70}")

    payloads = [bytes.fromhex(p['parsed']['decrypted_hex']) for p in type_packets]
    min_len = min(len(p) for p in payloads)

    print("\nPotential 16-bit values (big-endian, after header):")

    found = []
    for pos in range(66, min(min_len - 1, 250)):
        values_16 = [int.from_bytes(p[pos:pos+2], 'big') for p in payloads]
        unique = set(values_16)

        if len(unique) > 1 and max(values_16) > 0:
            min_v, max_v = min(values_16), max(values_16)

            # Check common scaling factors
            for scale, unit, expected_range in [
                (0.1, 'V', (10, 600)),      # Voltage
                (0.01, 'V', (100, 6000)),   # Battery voltage
                (0.1, 'W', (0, 50000)),     # Power
                (1, '%', (0, 100)),         # Percentage
                (0.1, '°C', (0, 1000)),     # Temperature
            ]:
                scaled_min = min_v * scale
                scaled_max = max_v * scale
                if expected_range[0] <= scaled_min <= expected_range[1] or \
                   expected_range[0] <= scaled_max <= expected_range[1]:
                    found.append((pos, min_v, max_v, scale, unit, scaled_min, scaled_max))
                    break

    # Print findings
    for pos, min_v, max_v, scale, unit, s_min, s_max in found[:20]:
        print(f"  @{pos:3d}-{pos+1}: {min_v:5d}-{max_v:5d} (×{scale} = {s_min:.1f}-{s_max:.1f}{unit})")


def analyze_diff_patterns(packets: list, packet_type: str):
    """Analyze what changes between consecutive packets."""
    packets_with_diff = [
        p for p in packets
        if p.get('parsed', {}).get('type_name') == packet_type
        and p.get('diff_from_previous')
    ]

    if len(packets_with_diff) < 3:
        return

    print(f"\n{'='*70}")
    print(f"DIFF PATTERN ANALYSIS: {packet_type}")
    print(f"{'='*70}")

    # Count offset changes
    offset_counts = defaultdict(int)
    for p in packets_with_diff:
        for change in p.get('diff_from_previous', []):
            if 'offset' in change:
                offset_counts[change['offset']] += 1

    total = len(packets_with_diff)
    print(f"\nMost frequently changing offsets ({total} packets with diffs):\n")

    for offset, count in sorted(offset_counts.items(), key=lambda x: -x[1])[:25]:
        pct = 100 * count / total
        bar = '█' * int(pct / 5)
        print(f"  @{offset:3d}: {count:4d} ({pct:5.1f}%) {bar}")

    # Identify likely timestamps
    always_change = [off for off, cnt in offset_counts.items() if cnt >= total * 0.9]
    if always_change:
        print(f"\nAlways changing (likely timestamp): offsets {sorted(always_change)}")


def analyze_server_commands(packets: list):
    """Analyze server-initiated packets."""
    server_packets = [
        p for p in packets
        if p.get('is_from_server')
    ]

    if not server_packets:
        return

    print(f"\n{'='*70}")
    print("SERVER -> DONGLE ANALYSIS")
    print(f"{'='*70}")

    # Group by type
    by_type = defaultdict(list)
    for p in server_packets:
        type_name = p.get('parsed', {}).get('type_name', 'UNKNOWN')
        by_type[type_name].append(p)

    for type_name, plist in sorted(by_type.items()):
        print(f"\n{type_name}: {len(plist)} packets")

        # Show payload lengths
        lengths = [p.get('parsed', {}).get('payload_length', 0) for p in plist]
        unique_lens = set(lengths)
        print(f"  Payload lengths: {sorted(unique_lens)}")

        # Show example
        if plist:
            ex = plist[0]
            raw = ex.get('parsed', {}).get('raw_hex', '')[:80]
            print(f"  Example: {raw}...")

            dec = ex.get('parsed', {}).get('decrypted_hex')
            if dec:
                print(f"  Decrypted: {dec[:80]}...")


def find_unknown_types(packets: list):
    """Document unknown packet types."""
    unknown = defaultdict(list)
    for p in packets:
        type_name = p.get('parsed', {}).get('type_name', '')
        if type_name.startswith('UNKNOWN'):
            type_hex = p.get('parsed', {}).get('type_hex', 'N/A')
            unknown[type_hex].append(p)

    if not unknown:
        print(f"\n{'='*70}")
        print("No unknown packet types found.")
        return

    print(f"\n{'='*70}")
    print("UNKNOWN PACKET TYPES")
    print(f"{'='*70}")

    for type_hex, plist in sorted(unknown.items()):
        print(f"\n{type_hex}: {len(plist)} packets")

        # Separate by direction
        from_dongle = [p for p in plist if 'DONGLE -> SERVER' in p.get('direction', '')]
        from_server = [p for p in plist if 'SERVER -> DONGLE' in p.get('direction', '')]

        if from_dongle:
            print(f"  From dongle: {len(from_dongle)}")
        if from_server:
            print(f"  From server: {len(from_server)} *** HIGH PRIORITY ***")

        # Show examples
        for i, p in enumerate(plist[:2]):
            ts = p.get('capture_timestamp', 'N/A')
            direction = p.get('direction', 'N/A')
            raw = p.get('parsed', {}).get('raw_hex', '')[:60]
            print(f"  Example {i+1}: {direction}")
            print(f"    Time: {ts}")
            print(f"    Raw: {raw}...")


def generate_offset_map(packets: list, packet_type: str):
    """Generate annotated offset map."""
    type_packets = [
        p for p in packets
        if p.get('parsed', {}).get('type_name') == packet_type
        and p.get('parsed', {}).get('decrypted_hex')
    ]

    if not type_packets:
        return

    print(f"\n{'='*70}")
    print(f"OFFSET MAP: {packet_type}")
    print(f"{'='*70}")

    payload = bytes.fromhex(type_packets[0]['parsed']['decrypted_hex'])
    print(f"\nPayload: {len(payload)} bytes")

    # Known fields
    print("\nKnown fields:")
    print("  [  0- 29] Datalogger serial (ASCII)")
    print("  [ 30- 59] Inverter serial (ASCII)")
    print("  [ 60- 65] Timestamp [Y-2000, M, D, H, M, S]")

    # Hex dump
    print(f"\nHex dump (first packet):\n")
    for row in range(0, min(len(payload), 256), 16):
        chunk = payload[row:row+16]
        hex_str = ' '.join(f'{b:02X}' for b in chunk).ljust(48)
        ascii_str = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
        print(f"  {row:3d}: {hex_str} |{ascii_str}|")


def main():
    global DATA_DIR

    # Parse arguments
    if len(sys.argv) > 1:
        DATA_DIR = Path(sys.argv[1])

    if not DATA_DIR.exists():
        print(f"Error: Directory not found: {DATA_DIR}")
        sys.exit(1)

    print(f"Analyzing: {DATA_DIR}\n")

    # Load packets
    packets = load_packets(DATA_DIR)
    if not packets:
        sys.exit(1)

    # Run analyses
    analyze_timing(packets)

    for ptype in ['DATA', 'ANNOUNCE']:
        analyze_byte_positions(packets, ptype)
        analyze_diff_patterns(packets, ptype)
        analyze_value_candidates(packets, ptype)
        generate_offset_map(packets, ptype)

    analyze_server_commands(packets)
    find_unknown_types(packets)

    print(f"\n{'='*70}")
    print("ANALYSIS COMPLETE")
    print(f"{'='*70}")
    print("\nTo save this output:")
    print(f"  python analyze.py > {DATA_DIR}/analysis.txt")


if __name__ == "__main__":
    main()
