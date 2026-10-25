#!/usr/bin/env python
"""
Growatt Gateway Watchdog

Mirrors the huawei-monitor modem watchdog pattern already used elsewhere
in this fleet (rancho-main-pi pings a target and reboots the cellular
modem after 3 consecutive failures): here the health signal is
growatt_gateway.py's /health endpoint instead of a ping.

Why this exists on top of the gateway's own soft reconnect: the incident
that motivated this whole rewrite (2026-07-18) was a USB-to-RS485 adapter
wedged at the kernel/USB level (`urb stopped: -32`). A pyserial-level
reconnect -- close the port, reopen it -- could not clear that; only a
full Pi reboot did. So this watchdog is the second, slower line of
defense: if the gateway has been unhealthy for long enough that its own
reconnect logic clearly isn't fixing it, reboot the host.

Before rebooting, it first tries a cheaper middle step: de-authorizing
and re-authorizing ONLY the USB-RS485 adapter (sysfs `authorized` 0 -> 1,
which drops and re-enumerates that one device) and restarting the
gateway. On 2026-10-25 that recovered a wedged adapter without a reboot
-- the July incident predates it, when only a driver unbind/rebind was
tried. The reboot stays as the fallback if the reset doesn't take.

A cooldown prevents reboot-looping if the adapter is genuinely dead (bad
cable, fried chip) -- after a reboot, this watchdog won't reboot again
for GATEWAY_WATCHDOG_COOLDOWN seconds even if checks keep failing, so a
truly broken adapter shows up as "still down after a reboot" for a human
to notice on-site, instead of the Pi endlessly rebooting itself.
"""
import json
import os
import subprocess
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

from growatt_common import load_env

ENV = load_env()

GATEWAY_HOST = ENV.get('GATEWAY_HOST', '127.0.0.1')
GATEWAY_PORT = int(ENV.get('GATEWAY_PORT', '8090'))
HEALTH_URL = f"http://{GATEWAY_HOST}:{GATEWAY_PORT}/health"

CHECK_INTERVAL = float(ENV.get('GATEWAY_WATCHDOG_INTERVAL', '60'))
FAILURE_LIMIT = int(ENV.get('GATEWAY_WATCHDOG_FAILURE_LIMIT', '10'))
UNHEALTHY_AGE = float(ENV.get('GATEWAY_WATCHDOG_UNHEALTHY_AGE', '300'))
COOLDOWN = float(ENV.get('GATEWAY_WATCHDOG_COOLDOWN', '3600'))
# vendor:product of the USB-RS485 adapter (Exar XR21V1410 on this inverter)
USB_ID = ENV.get('GATEWAY_WATCHDOG_USB_ID', '04e2:1410')
# Unhealthy checks before trying the USB reset; 0 disables it.
USB_RESET_AFTER = int(ENV.get('GATEWAY_WATCHDOG_USB_RESET_AFTER', '5'))
USB_ROOT = '/sys/bus/usb/devices'

STATE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.watchdog_state.json'
)


def is_healthy(health):
    """A gateway is healthy only if it's actually serving a fresh, real
    Modbus reading -- matches should_upload()'s definition in
    growatt_cloud.py so the watchdog and the cloud relay never disagree
    about what counts as "working"."""
    if health is None:
        return False
    if not health.get('modbus_connected'):
        return False
    if health.get('source') != 'modbus':
        return False
    age = health.get('age_seconds')
    if age is None or age > UNHEALTHY_AGE:
        return False
    return True


def check_health():
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"[{datetime.now()}] Watchdog: could not reach gateway: {e}")
        return None


def should_reset_usb(consecutive_failures, already_reset):
    """One USB reset per unhealthy episode, at exactly the configured
    check, and never once the reboot threshold has been reached."""
    return (USB_RESET_AFTER > 0
            and not already_reset
            and consecutive_failures == USB_RESET_AFTER
            and USB_RESET_AFTER < FAILURE_LIMIT)


def find_usb_device(usb_id=USB_ID, root=USB_ROOT):
    """sysfs path of the first USB device matching vendor:product, or
    None. Matched by ID rather than a fixed bus path so a replug into a
    different port still works -- and so we can never hit the wrong
    device (on a Pi 3B+, the neighbouring 1-1.1.1 is the LAN chip)."""
    vendor, product = usb_id.lower().split(':')
    try:
        names = sorted(os.listdir(root))
    except OSError:
        return None
    for name in names:
        path = os.path.join(root, name)
        try:
            with open(os.path.join(path, 'idVendor')) as f:
                v = f.read().strip()
            with open(os.path.join(path, 'idProduct')) as f:
                p = f.read().strip()
        except OSError:
            continue
        if (v, p) == (vendor, product):
            return path
    return None


def reset_usb_adapter():
    """Drop and re-enumerate only the adapter, with the gateway STOPPED
    for the duration. Order matters: if the gateway still holds
    /dev/ttyUSB0 open when the device comes back, the kernel can't reuse
    that node and names it ttyUSB1 -- and the gateway, configured for
    ttyUSB0, falls back to test data (seen on 2026-10-25)."""
    path = find_usb_device()
    if path is None:
        print(f"[{datetime.now()}] Watchdog: USB adapter {USB_ID} not found -- "
              f"skipping the USB reset")
        return False
    authorized = os.path.join(path, 'authorized')
    print(f"[{datetime.now()}] Watchdog: resetting USB adapter {USB_ID} at {path}")
    subprocess.run(['sudo', 'systemctl', 'stop', 'growatt-gateway'],
                   check=False, timeout=90)
    try:
        for value, pause in (('0', 3), ('1', 5)):
            subprocess.run(['sudo', 'tee', authorized], input=value.encode(),
                           stdout=subprocess.DEVNULL, check=False, timeout=15)
            time.sleep(pause)
    finally:
        subprocess.run(['sudo', 'systemctl', 'start', 'growatt-gateway'],
                       check=False, timeout=90)
    return True


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {'last_reboot': None}


def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)


def seconds_since_last_reboot(state):
    if not state.get('last_reboot'):
        return float('inf')
    last = datetime.fromisoformat(state['last_reboot'])
    return (datetime.now(timezone.utc) - last).total_seconds()


def reboot(state):
    print(f"[{datetime.now()}] Watchdog: rebooting to try to recover the Modbus adapter")
    state['last_reboot'] = datetime.now(timezone.utc).isoformat()
    save_state(state)
    subprocess.run(['sudo', 'reboot'], check=False)


def main():
    print("=" * 60)
    print("Growatt Gateway Watchdog")
    print("=" * 60)
    print(f"Health URL:     {HEALTH_URL}")
    print(f"Check interval: {CHECK_INTERVAL}s")
    print(f"Reboot after:   {FAILURE_LIMIT} consecutive unhealthy checks")
    print(f"Cooldown:       {COOLDOWN}s between reboots")
    print(f"USB reset:      {USB_ID} after {USB_RESET_AFTER} unhealthy checks"
          if USB_RESET_AFTER else "USB reset:      disabled")
    print("=" * 60)

    consecutive_failures = 0
    usb_reset_done = False
    state = load_state()

    while True:
        health = check_health()

        if is_healthy(health):
            if consecutive_failures > 0:
                how = "after a USB reset" if usb_reset_done else "on its own"
                print(f"[{datetime.now()}] Watchdog: gateway recovered {how} "
                      f"after {consecutive_failures} unhealthy check(s)")
            consecutive_failures = 0
            usb_reset_done = False
        else:
            consecutive_failures += 1
            print(f"[{datetime.now()}] Watchdog: unhealthy check "
                  f"{consecutive_failures}/{FAILURE_LIMIT} ({health})")

            if should_reset_usb(consecutive_failures, usb_reset_done):
                usb_reset_done = reset_usb_adapter()

            if consecutive_failures >= FAILURE_LIMIT:
                if seconds_since_last_reboot(state) < COOLDOWN:
                    print(f"[{datetime.now()}] Watchdog: still unhealthy but within the "
                          f"cooldown window since the last reboot -- not rebooting again, "
                          f"this needs a human to look at the hardware")
                else:
                    reboot(state)
                consecutive_failures = 0
                usb_reset_done = False

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
