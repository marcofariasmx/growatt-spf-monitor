"""Tests for growatt_gateway.py: the in-memory reading cache and the HTTP
handlers. These call the route functions directly (they're plain Python
functions) instead of going through a running server or FastAPI's
lifespan, so no real hardware or event loop is needed.
"""
import time

import growatt_gateway as gw

_SAMPLE_RAW = {
    'status': 12, 'vpv1': 764, 'vpv2': 0, 'ppv1': 960, 'ppv2': 0,
    'buck1_curr': 18, 'buck2_curr': 0,
    'output_watt': 740, 'output_va': 1210,
    'grid_charge': 0, 'grid_discharge': 0,
    'bat_volt': 5351, 'bat_soc': 96, 'bus_volt': 550, 'bat_watt': -160,
    'grid_volt': 0, 'grid_freq': 0, 'ac_in_watt': 0, 'ac_in_va': 0,
    'output_volt': 1200, 'output_freq': 6000,
    'output_curr': 62, 'inv_curr': 62, 'load_percent': 4,
    'inv_temp': 250, 'dcdc_temp': 240, 'buck1_temp': 240, 'buck2_temp': 0,
}


def test_snapshot_is_none_before_first_update():
    state = gw.GatewayState()
    assert state.snapshot() is None


def test_snapshot_reflects_last_update():
    state = gw.GatewayState()
    state.update(_SAMPLE_RAW, source='modbus')

    snap = state.snapshot()
    assert snap['source'] == 'modbus'
    assert snap['stale'] is False
    assert snap['reading']['bat_soc_pct'] == 96
    assert snap['raw_registers'] == _SAMPLE_RAW


def test_snapshot_marks_old_readings_stale(monkeypatch):
    monkeypatch.setattr(gw, 'STALE_AFTER', 0.05)
    state = gw.GatewayState()
    state.update(_SAMPLE_RAW, source='modbus')

    time.sleep(0.1)

    assert state.snapshot()['stale'] is True


def test_latest_endpoint_returns_503_with_no_reading(monkeypatch):
    monkeypatch.setattr(gw, 'state', gw.GatewayState())

    response = gw.latest()

    assert response.status_code == 503


def test_latest_endpoint_returns_reading_when_available(monkeypatch):
    fresh_state = gw.GatewayState()
    fresh_state.update(_SAMPLE_RAW, source='modbus')
    monkeypatch.setattr(gw, 'state', fresh_state)

    result = gw.latest()

    assert result['source'] == 'modbus'
    assert result['reading']['bat_soc_pct'] == 96


def test_latest_endpoint_flags_test_data_source(monkeypatch):
    """A consumer must be able to tell a fallback reading apart from a
    real one just from this response -- that's the whole point of the
    gateway surfacing `source` instead of hiding the fallback."""
    fresh_state = gw.GatewayState()
    fresh_state.update(_SAMPLE_RAW, source='test_data')
    monkeypatch.setattr(gw, 'state', fresh_state)

    result = gw.latest()

    assert result['source'] == 'test_data'


def test_health_endpoint_reports_no_inverter_by_default(monkeypatch):
    monkeypatch.setattr(gw, 'state', gw.GatewayState())
    monkeypatch.setattr(gw, '_inverter', None)

    health = gw.health()

    assert health['modbus_connected'] is False
    assert health['has_reading'] is False


def test_health_endpoint_reports_reading_age(monkeypatch):
    fresh_state = gw.GatewayState()
    fresh_state.update(_SAMPLE_RAW, source='modbus')
    monkeypatch.setattr(gw, 'state', fresh_state)

    health = gw.health()

    assert health['has_reading'] is True
    assert health['source'] == 'modbus'
    assert health['age_seconds'] >= 0
