"""Tests for growatt_watchdog.py's pure decision logic: what counts as
healthy, and the reboot cooldown window.
"""
from datetime import datetime, timedelta, timezone

import growatt_watchdog as wd


def test_is_healthy_false_when_gateway_unreachable():
    assert wd.is_healthy(None) is False


def test_is_healthy_false_when_modbus_not_connected():
    assert wd.is_healthy({'modbus_connected': False, 'source': 'modbus', 'age_seconds': 1}) is False


def test_is_healthy_false_when_source_is_test_data():
    """A gateway silently running on the fallback snapshot must count as
    unhealthy -- that's the exact situation this whole rewrite exists to
    stop treating as fine."""
    health = {'modbus_connected': True, 'source': 'test_data', 'age_seconds': 1}
    assert wd.is_healthy(health) is False


def test_is_healthy_false_when_reading_too_old():
    health = {'modbus_connected': True, 'source': 'modbus', 'age_seconds': wd.UNHEALTHY_AGE + 1}
    assert wd.is_healthy(health) is False


def test_is_healthy_true_for_a_fresh_modbus_reading():
    health = {'modbus_connected': True, 'source': 'modbus', 'age_seconds': 5}
    assert wd.is_healthy(health) is True


def test_seconds_since_last_reboot_is_infinite_if_never_rebooted():
    assert wd.seconds_since_last_reboot({'last_reboot': None}) == float('inf')


def test_seconds_since_last_reboot_measures_elapsed_time():
    ten_minutes_ago = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    elapsed = wd.seconds_since_last_reboot({'last_reboot': ten_minutes_ago})
    assert 595 < elapsed < 605
