# Complete Setup Guide - From Zero to Monitoring

This guide will take you from a fresh Raspberry Pi to a working Growatt monitoring system.

## Prerequisites

### Hardware Required
- ✅ Growatt SPF 3000TL LVM-48P inverter
- ✅ Raspberry Pi 4 (or any Linux system with USB)
- ✅ USB Type-B cable (standard printer cable)
- ✅ MicroSD card (16GB+) with Raspberry Pi OS
- ✅ Internet connection for Raspberry Pi

### Software Requirements
- Python 3.7 or higher
- pip (Python package installer)
- Git (optional, for cloning repository)

---

## Step 0: Prepare Raspberry Pi

### Fresh Raspberry Pi OS Installation

```bash
# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install required system packages
sudo apt-get install -y python3 python3-pip python3-venv git

# Verify Python version (should be 3.7+)
python3 --version
```

---

## Step 1: Hardware Connection

### Connect Inverter to Raspberry Pi

1. **Locate USB port on inverter**
   - On Growatt SPF 3000TL LVM-48P, it's a USB Type-B port
   - Usually on the bottom or side panel

2. **Connect USB cable**
   - Plug USB Type-B end into inverter
   - Plug USB Type-A end into Raspberry Pi

3. **Verify connection**
   ```bash
   # Check if device is detected
   ls -l /dev/ttyUSB*
   ```

   Expected output:
   ```
   crw-rw---- 1 root dialout 188, 0 Jan  7 10:00 /dev/ttyUSB0
   ```

4. **Check USB device details**
   ```bash
   dmesg | tail -20
   ```

   Look for:
   ```
   usb 1-1.3: new full-speed USB device
   usb 1-1.3: Manufacturer: Exar Corp.
   usb 1-1.3: Product: Exar USB UART
   cdc_acm 1-1.3:1.0: ttyUSB0: USB ACM device
   ```

---

## Step 2: Configure User Permissions

By default, serial ports require root access. Add your user to the `dialout` group:

```bash
# Add user to dialout group
sudo usermod -a -G dialout $USER

# Verify group membership
groups
```

**IMPORTANT:** Log out and log back in for changes to take effect!

```bash
# Log out
logout

# Or reboot
sudo reboot
```

After logging back in, verify:
```bash
groups | grep dialout
```

---

## Step 3: Install Monitoring Software

### Option A: Clone from Git Repository

```bash
# Navigate to home directory
cd ~

# Clone repository
git clone <repository-url> growatt-monitor
cd growatt-monitor
```

### Option B: Manual Setup

```bash
# Create project directory
cd ~
mkdir growatt-monitor
cd growatt-monitor

# Download files manually
# (Copy monitor.py, requirements.txt, etc.)
```

---

## Step 4: Create Python Virtual Environment

```bash
# Make sure you're in the project directory
cd ~/growatt-monitor

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Your prompt should now show (venv)
```

---

## Step 5: Install Python Dependencies

```bash
# Make sure virtual environment is activated
# You should see (venv) in your prompt

# Install dependencies
pip install -r requirements.txt

# Verify installation
pip list
```

Expected output should include:
```
pymodbus        3.11.4 (or higher)
pyserial        3.5 (or higher)
```

---

## Step 6: Test Connection

### Quick Connection Test

```bash
# Activate virtual environment if not already active
source venv/bin/activate

# Run test script
python scripts/test_connection.py
```

Expected output:
```
Testing connection to /dev/ttyUSB0...
✓ Connected successfully
✓ Device responding at address 1
✓ Read 7 registers successfully

Connection test PASSED!
```

### If Test Fails

**Error: Permission denied**
```bash
# Check permissions
ls -l /dev/ttyUSB0

# Add user to dialout group (if not done already)
sudo usermod -a -G dialout $USER

# Log out and back in
```

**Error: No such file or directory**
```bash
# Check if device is connected
lsusb

# Try alternate device name
ls -l /dev/ttyACM*
ls -l /dev/ttyUSB*

# Update PORT in monitor.py if needed
```

---

## Step 7: Run Monitoring Script

### Single Reading

```bash
# Activate virtual environment
source venv/bin/activate

# Run monitor
python monitor.py
```

### Expected Output

```
======================================================================
Growatt SPF 3000TL LVM-48P - Comprehensive Monitor
Using Official SPF Series Protocol V0.11
======================================================================

System Status: PV Charge & Discharge

--- PV Input ---
PV1 Voltage:  89.8 V
PV1 Power:    450.0 W

--- Battery ---
Battery Voltage: 53.20 V
Battery SOC:     95 %

--- AC Output (Inverter) ---
Output Voltage:  119.9 V
Output Frequency: 59.99 Hz
Output Power:    93.0 W

--- Temperatures ---
Inverter Temp:   27.1 °C
DC-DC Temp:      25.1 °C

======================================================================
```

---

## Step 8: Continuous Monitoring (Optional)

### Run Every Minute

```bash
# Use the continuous monitoring script
source venv/bin/activate
python examples/continuous_monitor.py
```

### Run as System Service

Create a systemd service:

```bash
# Create service file
sudo nano /etc/systemd/system/growatt-monitor.service
```

Add content:
```ini
[Unit]
Description=Growatt SPF Monitor
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/growatt-monitor
ExecStart=/home/pi/growatt-monitor/venv/bin/python /home/pi/growatt-monitor/examples/continuous_monitor.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service
sudo systemctl enable growatt-monitor

# Start service
sudo systemctl start growatt-monitor

# Check status
sudo systemctl status growatt-monitor

# View logs
sudo journalctl -u growatt-monitor -f
```

---

## Step 9: Customize Configuration

### Modify Device Settings

Edit `monitor.py`:

```python
# Change serial port if needed
PORT = '/dev/ttyUSB0'  # or /dev/ttyACM0

# Change device ID if configured differently
DEVICE_ID = 1  # Default for USB

# Adjust timeout if needed
timeout=3  # seconds
```

### Change Output Format

Modify the print statements in `monitor.py` to customize output format.

---

## Verification Checklist

After setup, verify:

- [ ] USB device appears as `/dev/ttyUSB0` or `/dev/ttyACM0`
- [ ] User is in `dialout` group
- [ ] Virtual environment activates successfully
- [ ] `pymodbus` and `pyserial` are installed
- [ ] Test script connects and reads registers
- [ ] Monitor script shows correct values
- [ ] AC Output Voltage shows ~120V or ~230V (not 0V)
- [ ] Battery voltage shows reasonable value (48-58V for 48V system)
- [ ] Temperatures are in reasonable range (20-40°C)

---

## Troubleshooting

### No Communication

**Check physical connection:**
```bash
lsusb | grep -i uart
dmesg | grep -i usb | tail -20
```

**Check permissions:**
```bash
groups | grep dialout
ls -l /dev/ttyUSB0
```

### Wrong Values

**Verify register scaling:**
- Battery voltage: multiply by 0.01 (register 17)
- AC voltage: multiply by 0.1 (register 22, NOT 20!)
- Temperature: multiply by 0.1 (register 25, 26)

**Check device ID:**
```bash
# USB connection uses device_id=1
# RS485 might use different address (1-247)
```

### Intermittent Readings

**Add delays between reads:**
```python
DELAY = 1.2  # seconds between register reads
```

**Reduce read speed:**
```python
timeout=5  # Increase timeout
```

---

## Next Steps

### Integration Options

1. **Home Assistant**
   - Use MQTT to publish data
   - Create sensors and automations

2. **Grafana Dashboard**
   - Log to InfluxDB
   - Create visualization dashboards

3. **Data Logging**
   - Use CSV export script
   - Analyze historical data

4. **Alerting**
   - Send notifications on low battery
   - Alert on faults/warnings

See `examples/` directory for implementation examples.

---

## Common Commands Reference

```bash
# Activate virtual environment
cd ~/growatt-monitor
source venv/bin/activate

# Run monitor
python monitor.py

# Deactivate virtual environment
deactivate

# Check logs (if running as service)
sudo journalctl -u growatt-monitor -f

# Restart service
sudo systemctl restart growatt-monitor

# Stop service
sudo systemctl stop growatt-monitor
```

---

## Support

If you encounter issues:

1. Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
2. Verify hardware connections
3. Review [REGISTER_MAP.md](REGISTER_MAP.md) for correct scaling
4. Check system logs: `dmesg | tail -50`

---

**Setup Time:** ~30 minutes for complete installation

**Status:** Ready for production use ✅
