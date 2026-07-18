# Growatt Protocol Capture Tool

A comprehensive toolkit for capturing, analyzing, and validating Growatt inverter communication protocols. Designed for reverse engineering the ShineWiFi-F dongle protocol to enable direct Pi-to-cloud communication.

## Overview

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Growatt   │     │  ShineWiFi  │     │   Growatt   │
│  Inverter   │────▶│   Dongle    │────▶│   Server    │
└─────────────┘     └─────────────┘     └─────────────┘
                          │
                          │ (network sniffing)
                          ▼
                    ┌─────────────┐
                    │ Raspberry   │
                    │     Pi      │
                    └─────────────┘
```

## Workflow

### Phase 1: Capture Ground Truth (24+ hours)

```bash
# Start long-term capture
cd tools/protocol_capture
sudo python capture.py 192.168.50.145

# Let it run for 24+ hours to capture:
# - Boot sequences
# - Regular DATA packets (every 5 min)
# - PING/PONG keepalives (every 3 min)
# - Server commands and configurations
# - Any rare/unusual packet types

# Press Ctrl+C when done
```

### Phase 2: Analyze Captured Data

```bash
# Run comprehensive analysis
python analyze.py

# Save analysis to file
python analyze.py > data/analysis.txt

# Open pcap in Wireshark for visual inspection
wireshark data/capture_*.pcap
```

### Phase 3: Validate Pi Implementation

```bash
# After connecting Pi to inverter, validate packets
python compare.py data/

# Or validate specific packet
python compare.py data/ "00010006..."

# Or validate from file
python compare.py data/ test_packets.jsonl
```

## Files

| File | Purpose |
|------|---------|
| `capture.py` | Main capture script (passive network sniffing) |
| `analyze.py` | Post-capture analysis (byte patterns, timing, values) |
| `compare.py` | Validate Pi packets against ground truth |
| `utils.py` | Shared utilities (XOR, CRC, parsing) |

## Output Directory Structure

```
data/
├── capture_YYYYMMDD_HH.pcap      # Raw packet capture (Wireshark)
├── packets_YYYYMMDD_HH.jsonl     # Parsed packets (JSON lines)
├── server_commands_YYYYMMDD_HH.jsonl  # Server→dongle packets
├── statistics.json               # Running statistics
└── summary_YYYYMMDD_HHMMSS.txt   # Final capture report
```

## Requirements

```bash
# Install tcpdump for packet capture
sudo apt install tcpdump

# Python 3.7+ (no additional packages needed)
```

## Usage Examples

### Capture

```bash
# Default (uses DONGLE_IP env or 192.168.50.145)
sudo python capture.py

# Specify dongle IP
sudo python capture.py 192.168.1.100

# Specify dongle IP and interface
sudo python capture.py 192.168.1.100 eth0

# Using environment variables
export DONGLE_IP=192.168.1.100
export CAPTURE_INTERFACE=eth0
sudo -E python capture.py
```

### Analyze

```bash
# Analyze default data directory
python analyze.py

# Analyze specific directory
python analyze.py /path/to/capture/data

# Save output
python analyze.py > analysis_report.txt
```

### Compare/Validate

```bash
# Interactive mode
python compare.py data/

# Validate single packet (hex string)
python compare.py data/ "00010005015d0104..."

# Validate packets from JSONL file
python compare.py data/ my_test_packets.jsonl
```

## What Gets Captured

### Packet Types

| Type | Code | Direction | Description |
|------|------|-----------|-------------|
| ANNOUNCE | 0x03 | D→S | Boot announcement (349 bytes) |
| DATA | 0x04 | D→S | Regular data upload (349 bytes) |
| PING | 0x16 | D→S | Keepalive request |
| PONG | 0x17 | S→D | Keepalive response |
| IDENTIFY | 0x19 | Both | Device identification |
| CONFIG | 0x18 | S→D | Server configuration/commands |
| ACK_ANNOUNCE | 0x13 | S→D | Acknowledge ANNOUNCE |
| ACK_DATA | 0x14 | S→D | Acknowledge DATA |

### Server Commands (High Priority)

Server-initiated packets are logged separately to `server_commands_*.jsonl` because they may contain:
- Configuration updates
- Time synchronization
- Firmware update triggers
- Remote parameter changes

## Analysis Features

### Byte Position Analysis
- Identifies static bytes (constants, padding)
- Identifies dynamic bytes (values, timestamps)
- Shows byte ranges observed in ground truth

### Timing Analysis
- Packet intervals by type
- Periodicity detection
- Anomaly identification

### Value Candidates
- Detects potential 16/32-bit values
- Suggests scaling factors (×0.1V, ×0.01V, etc.)
- Correlates with known register values

### Diff Tracking
- Tracks what changes between consecutive packets
- Identifies timestamp offsets
- Finds counter/sequence fields

## Packet Structure

```
┌──────┬──────┬────────┬─────┬──────┬─────────────────┬─────┐
│ TID  │ PID  │ Length │ UID │ Type │    Payload      │ CRC │
│ 2B   │ 2B   │ 2B     │ 1B  │ 1B   │   variable      │ 2B  │
└──────┴──────┴────────┴─────┴──────┴─────────────────┴─────┘
```

- **TID**: Transaction ID (big-endian)
- **PID**: Protocol ID (0x0005 or 0x0006 = encrypted)
- **Length**: Payload length including UID, Type, data, CRC
- **UID**: Unit ID (usually 1)
- **Type**: Message type (see table above)
- **Payload**: XOR encrypted with "Growatt" mask
- **CRC**: CRC-16/MODBUS (little-endian)

## Decrypted Payload Structure (DATA/ANNOUNCE)

```
Offset  Length  Description
──────  ──────  ───────────
0       30      Datalogger serial (ASCII, null-padded)
30      30      Inverter serial (ASCII, null-padded)
60      6       Timestamp [Y-2000, M, D, H, M, S]
66      ...     Inverter data (type-specific)
```

## Tips

1. **Capture Duration**: Run for at least 24 hours to capture all packet types and timing patterns.

2. **Network Setup**: Ensure Pi and dongle are on the same network segment for sniffing to work.

3. **Check Server Commands**: Always review `server_commands_*.jsonl` - these reveal what the server expects and sends.

4. **Unknown Types**: Any `UNKNOWN_0x??` types are flagged prominently - document and analyze these.

5. **Validation Before Production**: Use `compare.py` to validate your Pi implementation before deploying.

## Troubleshooting

### "Permission denied"
```bash
# Capture requires root
sudo python capture.py
```

### "No packets captured"
- Verify dongle IP address: `arp -a | grep -i growatt` or check router
- Verify interface: `ip link show`
- Check dongle is communicating: `sudo tcpdump -i wlan0 port 5279`

### "tcpdump not found"
```bash
sudo apt update && sudo apt install tcpdump
```

### Packets showing as malformed
- Check if dongle firmware uses different protocol version
- Verify XOR mask is correct ("Growatt")
- Check for non-standard packet types
