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


def test_should_reset_usb_only_at_the_configured_check():
    assert wd.should_reset_usb(wd.USB_RESET_AFTER - 1, False) is False
    assert wd.should_reset_usb(wd.USB_RESET_AFTER, False) is True
    assert wd.should_reset_usb(wd.USB_RESET_AFTER + 1, False) is False


def test_should_reset_usb_once_per_episode():
    assert wd.should_reset_usb(wd.USB_RESET_AFTER, True) is False


def test_should_reset_usb_disabled_when_zero(monkeypatch):
    monkeypatch.setattr(wd, 'USB_RESET_AFTER', 0)
    assert wd.should_reset_usb(0, False) is False


def _fake_usb(root, name, vendor, product):
    d = root / name
    d.mkdir()
    (d / 'idVendor').write_text(vendor + '\n')
    (d / 'idProduct').write_text(product + '\n')


def test_find_usb_device_matches_by_id_not_position(tmp_path):
    """The LAN chip sits next to the adapter on a Pi 3B+ -- matching by
    vendor:product must never pick it."""
    _fake_usb(tmp_path, '1-1.1.1', '0424', '7800')
    _fake_usb(tmp_path, '1-1.1.3', '04e2', '1410')
    (tmp_path / 'usb1').mkdir()  # a hub-like entry without id files
    assert wd.find_usb_device('04e2:1410', str(tmp_path)) == str(tmp_path / '1-1.1.3')


def test_find_usb_device_none_when_absent(tmp_path):
    _fake_usb(tmp_path, '1-1.1.1', '0424', '7800')
    assert wd.find_usb_device('04e2:1410', str(tmp_path)) is None
