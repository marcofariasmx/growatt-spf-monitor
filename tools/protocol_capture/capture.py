#!/usr/bin/env python3
"""
Growatt Protocol Long-Term Capture

Passively captures all traffic between the ShineWiFi-F dongle and Growatt
servers via network sniffing. Designed for 24+ hour captures to thoroughly
document all communication patterns.

Features:
- Passive sniffing (no dongle reconfiguration needed)
- Hourly log rotation
- Real-time packet parsing and decryption
- Server command tracking and alerting
- Comprehensive statistics

Usage:
    sudo python capture.py [dongle_ip] [interface]
    sudo python capture.py 192.168.50.145
    sudo python capture.py 192.168.50.145 eth0

Environment variables:
    DONGLE_IP         - Target dongle IP (default: 192.168.50.145)
    CAPTURE_INTERFACE - Network interface (default: wlan0)

Output:
    data/capture_YYYYMMDD_HH.pcap       - Raw packet capture
    data/packets_YYYYMMDD_HH.jsonl      - Parsed packets (JSON lines)
    data/server_commands_YYYYMMDD_HH.jsonl - Server-initiated packets
    data/statistics.json                - Running statistics
    data/summary_*.txt                  - Final summary report
"""

import subprocess
import time
import os
import sys
import json
import signal
import threading
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))
from utils import (
    parse_packet, find_growatt_payload, find_byte_differences,
    format_packet_summary, MSG_TYPES, EXPECTED_SERVER_RESPONSES,
    SERVER_COMMANDS
)

# Configuration
DONGLE_IP = os.environ.get('DONGLE_IP', '192.168.50.145')
INTERFACE = os.environ.get('CAPTURE_INTERFACE', 'wlan0')
GROWATT_PORT = 5279
OUTPUT_DIR = Path(__file__).parent / 'data'
STATS_INTERVAL = 300  # Print stats every 5 minutes
PARSE_INTERVAL = 10   # Parse new packets every 10 seconds

# Parse command line arguments
if len(sys.argv) > 1:
    DONGLE_IP = sys.argv[1]
if len(sys.argv) > 2:
    INTERFACE = sys.argv[2]

# Global state
stats = {
    'start_time': None,
    'total_packets': 0,
    'packets_by_type': defaultdict(int),
    'packets_by_direction': defaultdict(int),
    'unknown_types': set(),
    'unknown_server_types': set(),
    'server_commands': defaultdict(int),
    'server_commands_with_payload': 0,
    'bytes_captured': 0,
    'pcap_files': 0,
    'errors': 0,
}

# Current state
current_log_hour = None
json_log_file = None
server_cmd_log_file = None
tcpdump_proc = None
current_pcap_file = None
shutdown_requested = False

# Packet history for diff analysis
last_packets = {'ANNOUNCE': None, 'DATA': None}
processed_packet_ids = set()  # Track already processed packets


def extract_packets_from_pcap(pcap_file: Path) -> list:
    """Extract packets from pcap file using tcpdump."""
    if not pcap_file or not pcap_file.exists():
        return []

    try:
        result = subprocess.run(
            ['tcpdump', '-r', str(pcap_file), '-xx', '-n', '-tt', f'port {GROWATT_PORT}'],
            capture_output=True, text=True, timeout=60
        )

        packets = []
        current_hex = []
        current_timestamp = None
        current_direction = None

        for line in result.stdout.split('\n'):
            line = line.rstrip()

            # New packet header (timestamp line)
            if line and not line.startswith('\t') and not line.startswith(' '):
                # Save previous packet
                if current_hex:
                    hex_data = ''.join(current_hex)
                    packets.append({
                        'timestamp': current_timestamp,
                        'direction': current_direction,
                        'hex': hex_data,
                    })
                current_hex = []

                # Parse new packet header
                parts = line.split()
                if parts:
                    current_timestamp = parts[0]
                    # Determine direction
                    if DONGLE_IP in line:
                        # Check if dongle is source or destination
                        if '>' in line:
                            src_part = line.split('>')[0]
                            current_direction = 'DONGLE -> SERVER' if DONGLE_IP in src_part else 'SERVER -> DONGLE'
                        else:
                            current_direction = 'UNKNOWN'
                    else:
                        current_direction = 'UNKNOWN'

            # Hex data line (starts with tab + offset)
            elif line.startswith('\t0x'):
                parts = line.split(':')
                if len(parts) >= 2:
                    hex_part = parts[1].strip().replace(' ', '')
                    current_hex.append(hex_part)

        # Last packet
        if current_hex:
            packets.append({
                'timestamp': current_timestamp,
                'direction': current_direction,
                'hex': ''.join(current_hex),
            })

        return packets
    except subprocess.TimeoutExpired:
        print("[!] tcpdump timeout - pcap file may be locked")
        return []
    except Exception as e:
        print(f"[!] Error extracting packets: {e}")
        return []


def rotate_logs():
    """Rotate log files and tcpdump hourly."""
    global current_log_hour, json_log_file, server_cmd_log_file
    global tcpdump_proc, current_pcap_file, processed_packet_ids

    now = datetime.now()
    hour_key = now.strftime('%Y%m%d_%H')

    if hour_key == current_log_hour:
        return

    # Close existing files
    if json_log_file:
        json_log_file.close()
    if server_cmd_log_file:
        server_cmd_log_file.close()

    # Stop existing tcpdump
    if tcpdump_proc:
        tcpdump_proc.terminate()
        try:
            tcpdump_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            tcpdump_proc.kill()

    # Reset processed packets for new hour
    processed_packet_ids = set()

    # Create new files
    current_log_hour = hour_key
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    json_path = OUTPUT_DIR / f'packets_{hour_key}.jsonl'
    json_log_file = open(json_path, 'a')

    server_cmd_path = OUTPUT_DIR / f'server_commands_{hour_key}.jsonl'
    server_cmd_log_file = open(server_cmd_path, 'a')

    current_pcap_file = OUTPUT_DIR / f'capture_{hour_key}.pcap'
    stats['pcap_files'] += 1

    # Start new tcpdump
    try:
        tcpdump_proc = subprocess.Popen(
            [
                'tcpdump', '-i', INTERFACE,
                '-w', str(current_pcap_file),
                '-U',  # Packet-buffered output
                f'host {DONGLE_IP} and port {GROWATT_PORT}'
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE
        )
        print(f"\n[*] Capturing to {current_pcap_file.name}")
    except Exception as e:
        print(f"[!] Failed to start tcpdump: {e}")
        tcpdump_proc = None


def process_new_packets():
    """Process newly captured packets from current pcap file."""
    global stats

    if not current_pcap_file or not current_pcap_file.exists():
        return

    packets = extract_packets_from_pcap(current_pcap_file)

    for pkt_info in packets:
        # Create unique ID to avoid reprocessing
        pkt_id = f"{pkt_info['timestamp']}_{pkt_info['hex'][:40]}"
        if pkt_id in processed_packet_ids:
            continue
        processed_packet_ids.add(pkt_id)

        hex_data = pkt_info.get('hex', '')
        direction = pkt_info.get('direction', 'UNKNOWN')
        pkt_timestamp = pkt_info.get('timestamp', '')

        # Find and parse Growatt payload
        try:
            raw_bytes = bytes.fromhex(hex_data)
        except ValueError:
            continue

        growatt_data = find_growatt_payload(raw_bytes)
        if not growatt_data:
            continue

        parsed = parse_packet(growatt_data)
        if not parsed or 'error' in parsed:
            continue

        msg_type = parsed.get('type', 0)
        type_name = parsed.get('type_name', 'UNKNOWN')

        # Update statistics
        stats['total_packets'] += 1
        stats['bytes_captured'] += len(growatt_data)
        stats['packets_by_direction'][direction] += 1
        stats['packets_by_type'][type_name] += 1

        if type_name.startswith('UNKNOWN'):
            stats['unknown_types'].add(parsed.get('type_hex', 'N/A'))

        # Track server commands
        is_from_server = 'SERVER -> DONGLE' in direction
        is_server_command = False

        if is_from_server:
            stats['server_commands'][type_name] += 1
            if msg_type not in EXPECTED_SERVER_RESPONSES:
                is_server_command = True
                if type_name.startswith('UNKNOWN'):
                    stats['unknown_server_types'].add(parsed.get('type_hex', 'N/A'))
            if parsed.get('payload_length', 0) > 4:
                stats['server_commands_with_payload'] += 1
                is_server_command = True

        # Calculate diff from previous packet
        diff = None
        if type_name in ('ANNOUNCE', 'DATA') and parsed.get('decrypted_hex'):
            old = last_packets.get(type_name)
            if old:
                diff = find_byte_differences(old, parsed['decrypted_hex'])
            last_packets[type_name] = parsed['decrypted_hex']

        # Build log entry
        entry = {
            'capture_timestamp': datetime.now().isoformat(),
            'packet_timestamp': pkt_timestamp,
            'direction': direction,
            'is_from_server': is_from_server,
            'is_server_command': is_server_command,
            'parsed': parsed,
            'diff_from_previous': diff,
        }

        # Write to logs
        if json_log_file:
            json_log_file.write(json.dumps(entry) + '\n')
            json_log_file.flush()

        if is_from_server and server_cmd_log_file:
            server_cmd_log_file.write(json.dumps(entry) + '\n')
            server_cmd_log_file.flush()

        # Print to console
        print_packet(direction, parsed, is_server_command)


def print_packet(direction: str, parsed: dict, is_server_command: bool):
    """Print packet summary to console with colors."""
    timestamp = datetime.now().strftime('%H:%M:%S')
    type_name = parsed.get('type_name', 'UNKNOWN')
    msg_type = parsed.get('type', 0)
    length = parsed.get('raw_length', 0)
    payload_len = parsed.get('payload_length', 0)

    is_from_server = 'SERVER -> DONGLE' in direction
    arrow = '←' if is_from_server else '→'

    # Colors
    COLORS = {
        'ANNOUNCE': '\033[93m', 'DATA': '\033[92m',
        'PING': '\033[94m', 'PONG': '\033[94m',
        'IDENTIFY': '\033[95m', 'CONFIG': '\033[96m',
        'ACK_ANNOUNCE': '\033[90m', 'ACK_DATA': '\033[90m',
    }
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[91m'
    YELLOW = '\033[93m'

    color = COLORS.get(type_name, RESET)

    # Prefix for important packets
    prefix = ''
    if is_from_server:
        if type_name.startswith('UNKNOWN'):
            prefix = f'{BOLD}{RED}[!!! UNKNOWN SERVER TYPE !!!] {RESET}'
            color = RED
        elif is_server_command:
            prefix = f'{BOLD}{YELLOW}[SERVER CMD] {RESET}'

    crc_ok = ' [CRC OK]' if parsed.get('crc_valid') else ''

    extra = ''
    if is_from_server and payload_len > 4:
        extra = f' payload={payload_len}B'

    print(f"[{timestamp}] {arrow} {prefix}{color}{type_name:12}{RESET} {length:4}B{crc_ok}{extra}")


def print_statistics():
    """Print capture statistics."""
    if not stats['start_time']:
        return

    runtime = datetime.now() - stats['start_time']
    hours = max(runtime.total_seconds() / 3600, 0.001)

    print("\n" + "=" * 70)
    print(f"CAPTURE STATISTICS (running {runtime})")
    print("=" * 70)
    print(f"Total packets: {stats['total_packets']:,}")
    print(f"Total bytes: {stats['bytes_captured']:,}")
    print(f"PCAP files: {stats['pcap_files']}")

    if stats['packets_by_type']:
        print("\nPackets by type:")
        for ptype, count in sorted(stats['packets_by_type'].items(), key=lambda x: -x[1]):
            rate = count / hours
            print(f"  {ptype:20} {count:6,}  ({rate:.1f}/hour)")

    if stats['packets_by_direction']:
        print("\nBy direction:")
        for direction, count in sorted(stats['packets_by_direction'].items()):
            print(f"  {direction:25} {count:6,}")

    if stats['server_commands']:
        print("\nServer -> Dongle:")
        for cmd, count in sorted(stats['server_commands'].items(), key=lambda x: -x[1]):
            print(f"  {cmd:20} {count:6,}")

    if stats['unknown_server_types']:
        print(f"\n\033[91m*** UNKNOWN SERVER TYPES: {stats['unknown_server_types']} ***\033[0m")

    if stats['unknown_types']:
        print(f"\nUnknown dongle types: {stats['unknown_types']}")

    print("=" * 70 + "\n")


def save_statistics():
    """Save statistics to JSON file."""
    stats_file = OUTPUT_DIR / 'statistics.json'
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    stats_copy = {
        'start_time': stats['start_time'].isoformat() if stats['start_time'] else None,
        'last_update': datetime.now().isoformat(),
        'total_packets': stats['total_packets'],
        'bytes_captured': stats['bytes_captured'],
        'pcap_files': stats['pcap_files'],
        'errors': stats['errors'],
        'packets_by_type': dict(stats['packets_by_type']),
        'packets_by_direction': dict(stats['packets_by_direction']),
        'server_commands': dict(stats['server_commands']),
        'server_commands_with_payload': stats['server_commands_with_payload'],
        'unknown_types': list(stats['unknown_types']),
        'unknown_server_types': list(stats['unknown_server_types']),
    }

    with open(stats_file, 'w') as f:
        json.dump(stats_copy, f, indent=2)


def generate_summary() -> Path:
    """Generate final summary report."""
    summary_file = OUTPUT_DIR / f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    runtime = datetime.now() - stats['start_time'] if stats['start_time'] else timedelta(0)
    hours = max(runtime.total_seconds() / 3600, 0.001)

    with open(summary_file, 'w') as f:
        f.write("=" * 80 + "\n")
        f.write("GROWATT PROTOCOL CAPTURE - FINAL SUMMARY\n")
        f.write("=" * 80 + "\n\n")

        f.write(f"Target dongle: {DONGLE_IP}\n")
        f.write(f"Interface: {INTERFACE}\n")
        f.write(f"Started: {stats['start_time']}\n")
        f.write(f"Ended: {datetime.now()}\n")
        f.write(f"Runtime: {runtime}\n\n")

        f.write(f"Total packets: {stats['total_packets']:,}\n")
        f.write(f"Total bytes: {stats['bytes_captured']:,}\n")
        f.write(f"PCAP files: {stats['pcap_files']}\n\n")

        f.write("-" * 40 + "\n")
        f.write("PACKETS BY TYPE\n")
        f.write("-" * 40 + "\n")
        for ptype, count in sorted(stats['packets_by_type'].items(), key=lambda x: -x[1]):
            f.write(f"  {ptype:20} {count:8,}  ({count/hours:6.1f}/hour)\n")

        f.write("\n" + "-" * 40 + "\n")
        f.write("PACKETS BY DIRECTION\n")
        f.write("-" * 40 + "\n")
        for direction, count in sorted(stats['packets_by_direction'].items()):
            f.write(f"  {direction:25} {count:8,}\n")

        f.write("\n" + "-" * 40 + "\n")
        f.write("SERVER -> DONGLE COMMUNICATION\n")
        f.write("-" * 40 + "\n")
        if stats['server_commands']:
            for cmd, count in sorted(stats['server_commands'].items(), key=lambda x: -x[1]):
                f.write(f"  {cmd:20} {count:8,}\n")
            f.write(f"\nServer packets with payload: {stats['server_commands_with_payload']}\n")
        else:
            f.write("  No server packets captured\n")

        if stats['unknown_server_types']:
            f.write("\n" + "-" * 40 + "\n")
            f.write("*** UNKNOWN SERVER PACKET TYPES ***\n")
            f.write("-" * 40 + "\n")
            for utype in sorted(stats['unknown_server_types']):
                f.write(f"  {utype}\n")
            f.write("\n!!! HIGH PRIORITY: Analyze server_commands_*.jsonl !!!\n")

        if stats['unknown_types']:
            f.write("\n" + "-" * 40 + "\n")
            f.write("Unknown dongle packet types:\n")
            for utype in sorted(stats['unknown_types']):
                f.write(f"  {utype}\n")

        f.write("\n" + "-" * 40 + "\n")
        f.write("OUTPUT FILES\n")
        f.write("-" * 40 + "\n")
        for fpath in sorted(OUTPUT_DIR.glob('*')):
            if fpath.is_file():
                f.write(f"  {fpath.name:45} {fpath.stat().st_size:12,} bytes\n")

        f.write("\n" + "-" * 40 + "\n")
        f.write("NEXT STEPS\n")
        f.write("-" * 40 + "\n")
        f.write("1. Analyze capture:  python analyze.py\n")
        f.write("2. Open in Wireshark: wireshark data/capture_*.pcap\n")
        f.write("3. Check server commands: data/server_commands_*.jsonl\n")
        f.write("4. Build comparison: python compare.py (after connecting Pi)\n")

    print(f"\n[*] Summary saved to: {summary_file}")
    return summary_file


def background_loop():
    """Background thread for stats and packet processing."""
    last_stats_time = time.time()
    last_parse_time = time.time()

    while not shutdown_requested:
        time.sleep(1)

        # Process packets periodically
        if time.time() - last_parse_time >= PARSE_INTERVAL:
            try:
                process_new_packets()
            except Exception as e:
                print(f"[!] Parse error: {e}")
                stats['errors'] += 1
            last_parse_time = time.time()

        # Print stats periodically
        if time.time() - last_stats_time >= STATS_INTERVAL:
            print_statistics()
            save_statistics()
            last_stats_time = time.time()


def main():
    global stats, shutdown_requested

    print("=" * 70)
    print("GROWATT PROTOCOL CAPTURE")
    print("=" * 70)
    print(f"\nTarget: {DONGLE_IP}")
    print(f"Interface: {INTERFACE}")
    print(f"Output: {OUTPUT_DIR}")
    print("\nPassive sniffing - no dongle reconfiguration needed.")
    print("Press Ctrl+C to stop.\n")

    # Check root
    if os.geteuid() != 0:
        print("[!] Root required. Run with: sudo python capture.py")
        sys.exit(1)

    # Check tcpdump
    if subprocess.run(['which', 'tcpdump'], capture_output=True).returncode != 0:
        print("[!] tcpdump not found. Install: sudo apt install tcpdump")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stats['start_time'] = datetime.now()

    # Signal handlers
    def handle_signal(sig, frame):
        global shutdown_requested
        print("\n\n[*] Stopping...")
        shutdown_requested = True

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Start capture
    rotate_logs()

    print(f"[*] Started at {stats['start_time']}")
    print(f"[*] Waiting for traffic...\n")

    # Background processing thread
    bg_thread = threading.Thread(target=background_loop, daemon=True)
    bg_thread.start()

    # Main loop - just rotate logs hourly
    try:
        while not shutdown_requested:
            time.sleep(60)
            rotate_logs()
    finally:
        # Cleanup
        if tcpdump_proc:
            tcpdump_proc.terminate()
            try:
                tcpdump_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                tcpdump_proc.kill()

        if json_log_file:
            json_log_file.close()
        if server_cmd_log_file:
            server_cmd_log_file.close()

        # Final processing
        try:
            process_new_packets()
        except:
            pass

        print_statistics()
        save_statistics()
        generate_summary()

        print(f"\n[*] Done! Files in: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
