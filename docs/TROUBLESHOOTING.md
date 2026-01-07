# Troubleshooting Guide

Common issues and solutions for Growatt SPF monitoring system.

---

## Connection Issues

### Problem: Device Not Found (`/dev/ttyUSB0` missing)

**Symptoms:**
```
FileNotFoundError: [Errno 2] No such file or directory: '/dev/ttyUSB0'
```

**Solutions:**

1. **Check if USB device is connected:**
   ```bash
   lsusb | grep -i "uart\|serial\|exar"
   ```

   Should show:
   ```
   Bus 001 Device 004: ID 04e2:1410 Exar Corp. XR21V1410 USB-UART
   ```

2. **Try alternate device names:**
   ```bash
   ls -l /dev/ttyUSB*
   ls -l /dev/ttyACM*
   ls -l /dev/serial/by-id/*
   ```

   Update `PORT` in `monitor.py` if device is at different path.

3. **Check dmesg for USB events:**
   ```bash
   dmesg | grep -i "usb\|tty" | tail -30
   ```

4. **Replug USB cable:**
   ```bash
   # Unplug USB from Raspberry Pi
   # Wait 5 seconds
   # Plug back in
   dmesg | tail -20
   ```

---

### Problem: Permission Denied

**Symptoms:**
```
PermissionError: [Errno 13] Permission denied: '/dev/ttyUSB0'
```

**Solutions:**

1. **Check current permissions:**
   ```bash
   ls -l /dev/ttyUSB0
   ```

   Shows:
   ```
   crw-rw---- 1 root dialout 188, 0 Jan  7 10:00 /dev/ttyUSB0
   ```

2. **Add user to dialout group:**
   ```bash
   sudo usermod -a -G dialout $USER
   ```

3. **Verify group membership:**
   ```bash
   groups
   ```

   Should include `dialout`

4. **Log out and back in:**
   ```bash
   # IMPORTANT: Changes only take effect after logout/login
   logout
   # Or reboot
   sudo reboot
   ```

5. **Temporary fix (not recommended):**
   ```bash
   sudo chmod 666 /dev/ttyUSB0
   # Note: Resets after reboot
   ```

---

### Problem: Connection Timeout

**Symptoms:**
```
ModbusIOException: [Connection] Modbus Error: [Connection] No Response received
```

**Solutions:**

1. **Increase timeout:**
   ```python
   client = ModbusSerialClient(
       port=PORT,
       timeout=5  # Increase from 3 to 5 seconds
   )
   ```

2. **Add delay between reads:**
   ```python
   import time
   time.sleep(1.2)  # Wait between register reads
   ```

3. **Check baud rate:**
   ```python
   # Verify baud rate is 9600
   client = ModbusSerialClient(
       baudrate=9600  # NOT 115200 or other values
   )
   ```

4. **Verify device ID:**
   ```python
   # USB connection typically uses device_id=1
   result = client.read_input_registers(address=0, count=1, device_id=1)
   ```

---

## Data Reading Issues

### Problem: All Registers Return 0 or None

**Symptoms:**
- All values show 0.0
- All reads return `None`

**Solutions:**

1. **Verify inverter is powered on:**
   - Check LCD display is active
   - Verify battery voltage > 40V

2. **Test with simple script:**
   ```bash
   python scripts/test_connection.py
   ```

3. **Try reading holding registers:**
   ```python
   # Some inverters respond to holding registers better
   result = client.read_holding_registers(address=30, count=1, device_id=1)
   print(result.registers[0])  # Should show modbus address (usually 1)
   ```

4. **Power cycle inverter:**
   ```bash
   # Turn off inverter
   # Wait 20 seconds
   # Turn back on
   # Wait for full boot (30+ seconds)
   ```

---

### Problem: AC Output Voltage Shows 0V

**Symptoms:**
- AC voltage reads 0.0V
- But load is clearly running

**Solution:**

**You're reading the WRONG register!**

❌ **Wrong (Register 20):**
```python
ac_volt = read_u16(client, 20) * 0.1  # This is GRID INPUT voltage!
```

✅ **Correct (Register 22):**
```python
ac_volt = read_u16(client, 22) * 0.1  # This is INVERTER OUTPUT voltage!
```

**Explanation:**
- Register 20 = Grid **INPUT** voltage (0V when off-grid)
- Register 22 = Inverter **OUTPUT** voltage (actual house voltage)

---

### Problem: Battery Voltage Shows Wrong Value

**Symptoms:**
- Battery voltage shows 532V instead of 53.2V
- Or shows 5.3V instead of 53V

**Solution:**

**Wrong scaling factor!**

❌ **Wrong:**
```python
bat_volt = read_u16(client, 17) * 0.1  # Wrong scaling!
```

✅ **Correct:**
```python
bat_volt = read_u16(client, 17) * 0.01  # Battery uses 0.01 scaling!
```

**Remember:**
- Battery voltage (reg 17): multiply by **0.01**
- Most other voltages (AC, PV): multiply by **0.1**

---

### Problem: Temperature Shows Unrealistic Values

**Symptoms:**
- Temperature shows 227°C or 23°C in 100°F room

**Solutions:**

1. **Check scaling factor:**
   ```python
   # Temperature uses 0.1 scaling
   temp = read_u16(client, 25) * 0.1  # NOT 1.0
   ```

2. **Verify register number:**
   - Register 25 = Inverter temperature
   - Register 26 = DC-DC temperature
   - NOT register 27 (that's load percentage!)

---

### Problem: Load Percentage Shows Wrong Value

**Symptoms:**
- Load shows 30% when only 3% is being used

**Solution:**

**Wrong scaling!**

```python
# Load percentage uses 0.1 scaling
load_pct = read_u16(client, 27) * 0.1  # NOT 1.0
```

Example: Raw value 40 = 4.0% (not 40%)

---

### Problem: 32-bit Values Are Wrong

**Symptoms:**
- PV power shows as 65536W instead of 450W
- Energy totals are wildly incorrect

**Solution:**

**Incorrect 32-bit reading:**

❌ **Wrong:**
```python
# Reading only high word
ppv1 = read_u16(client, 3) * 0.1
```

✅ **Correct:**
```python
# Read both high and low words
def read_u32(client, address):
    result = client.read_input_registers(address=address, count=2, device_id=1)
    high = result.registers[0]
    low = result.registers[1]
    return (high << 16) | low

ppv1 = read_u32(client, 3) * 0.1  # Reads registers 3-4
```

---

## Python Environment Issues

### Problem: Module Not Found

**Symptoms:**
```
ModuleNotFoundError: No module named 'pymodbus'
```

**Solutions:**

1. **Activate virtual environment:**
   ```bash
   cd ~/growatt-monitor
   source venv/bin/activate
   # Prompt should show (venv)
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Verify installation:**
   ```bash
   pip list | grep pymodbus
   ```

---

### Problem: Wrong Python Version

**Symptoms:**
```
SyntaxError: invalid syntax
```

**Solutions:**

1. **Check Python version:**
   ```bash
   python --version
   # Should be 3.7 or higher
   ```

2. **Use python3 explicitly:**
   ```bash
   python3 monitor.py
   ```

3. **Update Python:**
   ```bash
   sudo apt-get update
   sudo apt-get install python3 python3-pip
   ```

---

## Hardware Issues

### Problem: Intermittent Connection

**Symptoms:**
- Sometimes works, sometimes doesn't
- Random timeouts

**Solutions:**

1. **Check USB cable quality:**
   - Try different USB cable
   - Avoid long cables (>3 meters)
   - Avoid USB hubs

2. **Check USB port:**
   - Try different USB port on Raspberry Pi
   - Avoid USB 3.0 ports if issues persist

3. **Power issues:**
   - Ensure Raspberry Pi has adequate power supply
   - Check for undervoltage warnings:
     ```bash
     vcgencmd get_throttled
     ```

4. **Add USB reset:**
   ```bash
   # Reset USB device
   sudo usbreset /dev/ttyUSB0
   # Or unplug/replug USB cable
   ```

---

### Problem: Inverter LCD Shows "COM Error"

**Symptoms:**
- Inverter displays communication error
- Modbus stops responding

**Solutions:**

1. **Too many commands:**
   - Reduce read frequency
   - Add delays between reads:
     ```python
     time.sleep(1.0)  # Minimum 850ms, recommended 1s
     ```

2. **Restart inverter:**
   - Power cycle the inverter
   - Wait 30+ seconds for full boot

3. **Check for multiple connections:**
   - Only one device should communicate at a time
   - Disconnect WiFi dongle if present

---

## Performance Issues

### Problem: Slow Response Time

**Symptoms:**
- Each read takes several seconds
- Script hangs

**Solutions:**

1. **Optimize register reads:**
   ```python
   # Read multiple registers at once
   result = client.read_input_registers(address=1, count=10, device_id=1)
   # Instead of 10 separate reads
   ```

2. **Reduce timeout:**
   ```python
   client = ModbusSerialClient(
       timeout=1.5  # Reduce if reliable
   )
   ```

3. **Skip unnecessary registers:**
   - Only read registers you need
   - Comment out unused sections

---

## Validation Issues

### Problem: Unsure if Values Are Correct

**Solutions:**

1. **Cross-check with LCD:**
   - Compare battery voltage on LCD vs reading
   - Compare PV voltage
   - Compare AC output voltage

2. **Sanity checks:**
   ```python
   # Battery voltage (48V system)
   assert 40 < bat_volt < 60, f"Battery voltage {bat_volt}V out of range!"

   # AC output (120V system)
   assert 110 < ac_volt < 130, f"AC voltage {ac_volt}V out of range!"

   # Temperature
   assert 0 < temp < 80, f"Temperature {temp}°C out of range!"
   ```

3. **Test with known load:**
   ```bash
   # Turn on 1500W kettle
   # Output power should increase by ~1500W
   # Load percentage should increase accordingly
   ```

---

## Debug Mode

### Enable Detailed Logging

```python
import logging

logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.DEBUG)

# Now run your script
# Will show all Modbus communication
```

### Raw Register Dump

```python
# Dump all registers 0-50
for i in range(50):
    try:
        val = read_u16(client, i)
        print(f"Register {i}: {val} (0x{val:04X})")
    except:
        print(f"Register {i}: FAILED")
    time.sleep(0.1)
```

---

## Quick Diagnostic Checklist

Run through this checklist:

- [ ] USB device shows in `lsusb`
- [ ] `/dev/ttyUSB0` (or `/dev/ttyACM0`) exists
- [ ] User is in `dialout` group (check `groups`)
- [ ] Logged out and back in after adding to group
- [ ] Virtual environment activated (`(venv)` in prompt)
- [ ] `pymodbus` installed (`pip list | grep pymodbus`)
- [ ] Inverter is powered on (LCD active)
- [ ] Battery voltage > 40V
- [ ] Using device_id=1 for USB connection
- [ ] Baud rate is 9600
- [ ] Reading register 22 (not 20) for AC output voltage
- [ ] Using correct scaling factors (0.01 for battery, 0.1 for others)
- [ ] Delay of 1+ second between reads

---

## Still Having Issues?

1. **Review documentation:**
   - [Setup Guide](SETUP_GUIDE.md)
   - [Register Map](REGISTER_MAP.md)

2. **Test with minimal script:**
   ```python
   from pymodbus.client import ModbusSerialClient

   client = ModbusSerialClient(port='/dev/ttyUSB0', baudrate=9600, timeout=3)
   client.connect()
   result = client.read_input_registers(address=18, count=1, device_id=1)
   print(f"Battery SOC: {result.registers[0]}%")
   client.close()
   ```

3. **Check system logs:**
   ```bash
   dmesg | tail -50
   journalctl -xe | tail -50
   ```

4. **Hardware test:**
   - Test on different computer
   - Test with different USB cable
   - Test with different inverter (if available)

---

**Last Updated:** 2026-01-07
