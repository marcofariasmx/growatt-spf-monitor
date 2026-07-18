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
    print("=" * 60)

    consecutive_failures = 0
    state = load_state()

    while True:
        health = check_health()

        if is_healthy(health):
            if consecutive_failures > 0:
                print(f"[{datetime.now()}] Watchdog: gateway recovered on its own "
                      f"after {consecutive_failures} unhealthy check(s)")
            consecutive_failures = 0
        else:
            consecutive_failures += 1
            print(f"[{datetime.now()}] Watchdog: unhealthy check "
                  f"{consecutive_failures}/{FAILURE_LIMIT} ({health})")

            if consecutive_failures >= FAILURE_LIMIT:
                if seconds_since_last_reboot(state) < COOLDOWN:
                    print(f"[{datetime.now()}] Watchdog: still unhealthy but within the "
                          f"cooldown window since the last reboot -- not rebooting again, "
                          f"this needs a human to look at the hardware")
                else:
                    reboot(state)
                consecutive_failures = 0

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
