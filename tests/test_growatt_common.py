"""Tests for growatt_common: register scaling, test-data loading, and the
Modbus reader's error handling.
"""
import os

import pytest

from growatt_common import InverterReader, load_test_data, scale_reading


def test_scale_reading_applies_correct_factors():
    raw = {
        'status': 12, 'vpv1': 764, 'vpv2': 0, 'ppv1': 960, 'ppv2': 0,
        'output_watt': 740, 'output_va': 1210,
        'bat_volt': 5351, 'bat_soc': 96, 'bat_watt': -160,
        'bus_volt': 550, 'grid_volt': 0, 'grid_freq': 6000,
        'output_volt': 1200, 'output_freq': 6000,
        'load_percent': 4, 'inv_temp': 250, 'dcdc_temp': 240,
    }
    scaled = scale_reading(raw)

    assert scaled['status'] == 12
    assert scaled['vpv1_v'] == pytest.approx(76.4)
    assert scaled['ppv1_w'] == pytest.approx(96.0)
    assert scaled['output_w'] == pytest.approx(74.0)
    assert scaled['output_va'] == pytest.approx(121.0)
    assert scaled['bat_volt_v'] == pytest.approx(53.51)
    assert scaled['bat_soc_pct'] == 96
    assert scaled['bat_watt_w'] == pytest.approx(-16.0)
    assert scaled['grid_freq_hz'] == pytest.approx(60.0)


def test_load_test_data_from_example_fixture():
    fixture = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'test_data', 'inverter_snapshot.example.json'
    )
    data = load_test_data(fixture)

    assert data is not None
    assert isinstance(data['status'], int)
    assert isinstance(data['ppv1'], int)
    # 32-bit fields must be combined from two registers, not truncated to one
    assert data['output_watt'] >= 0


def test_load_test_data_missing_file_returns_none(tmp_path):
    missing = tmp_path / "does_not_exist.json"
    assert load_test_data(str(missing)) is None


class _FakeRegistersResult:
    """Mimics a successful pymodbus ReadInputRegistersResponse."""

    def __init__(self, registers):
        self.registers = registers


class _FakeErrorResult:
    """Mimics a pymodbus ExceptionResponse: no .registers attribute."""

    def __str__(self):
        return "Exception Response(132, 4, IllegalAddress)"


class _FakeModbusClient:
    """Stands in for pymodbus's ModbusSerialClient in tests. Addresses not
    given an explicit response fall back to a default so read_all() can be
    exercised without enumerating every register.
    """

    def __init__(self, responses=None, default=None):
        self._responses = responses or {}
        self._default = default if default is not None else _FakeRegistersResult([0, 0])

    def read_input_registers(self, address, count, device_id):
        result = self._responses.get(address, self._default)
        if isinstance(result, Exception):
            raise result
        return result


def _reader_with_fake_client(responses=None, default=None):
    reader = InverterReader(port='/dev/fake', baudrate=9600, device_id=1)
    reader.client = _FakeModbusClient(responses, default)
    return reader


def test_read_u16_returns_value_on_success():
    reader = _reader_with_fake_client({0: _FakeRegistersResult([12])})
    assert reader._read_u16(0) == 12


def test_read_u16_returns_zero_on_error_response():
    """This is the exact failure mode from the 2026-07-17 incident: a
    failing USB-serial adapter caused every register read to come back as
    an error response, which the old code silently turned into 0 instead
    of surfacing the failure."""
    reader = _reader_with_fake_client({0: _FakeErrorResult()})
    assert reader._read_u16(0) == 0


def test_read_u16_returns_zero_on_exception():
    reader = _reader_with_fake_client({0: IOError("timed out")})
    assert reader._read_u16(0) == 0


def test_read_u32_combines_high_and_low_words():
    reader = _reader_with_fake_client({3: _FakeRegistersResult([1, 44])})
    assert reader._read_u32(3) == (1 << 16) | 44


def test_read_s32_handles_negative_values():
    # 0xFFFFFF60 as a signed 32-bit value is -160 (charging 16.0W)
    reader = _reader_with_fake_client({77: _FakeRegistersResult([0xFFFF, 0xFF60])})
    assert reader._read_s32(77) == -160


def test_read_s32_handles_positive_values():
    reader = _reader_with_fake_client({77: _FakeRegistersResult([0x0000, 0x00A0])})
    assert reader._read_s32(77) == 160


def test_read_all_returns_every_key_scale_reading_needs():
    reader = _reader_with_fake_client()
    data = reader.read_all()

    for key in ('status', 'vpv1', 'vpv2', 'ppv1', 'ppv2', 'output_watt',
                'output_va', 'bat_volt', 'bat_soc', 'bat_watt', 'bus_volt',
                'grid_volt', 'grid_freq', 'output_volt', 'output_freq',
                'load_percent', 'inv_temp', 'dcdc_temp'):
        assert key in data

    # Must not raise -- scale_reading() requires exactly these keys
    scale_reading(data)


def test_all_reads_failed_is_false_when_everything_succeeds():
    reader = _reader_with_fake_client(default=_FakeRegistersResult([0, 0]))
    reader.read_all()
    assert reader.all_reads_failed is False


def test_all_reads_failed_is_true_when_every_register_errors():
    """This is the exact scenario from the 2026-07-17 incident: the
    adapter accepts a connection but every subsequent register read
    fails. The gateway needs to be able to tell this apart from a
    legitimate reading full of real zeros."""
    reader = _reader_with_fake_client(default=_FakeErrorResult())
    reader.read_all()
    assert reader.all_reads_failed is True


def test_all_reads_failed_is_false_with_a_partial_failure():
    responses = {0: _FakeErrorResult()}
    reader = _reader_with_fake_client(responses, default=_FakeRegistersResult([0, 0]))
    reader.read_all()
    assert reader.all_reads_failed is False


def test_read_all_resets_counters_between_calls():
    reader = _reader_with_fake_client(default=_FakeErrorResult())
    reader.read_all()
    assert reader.all_reads_failed is True

    reader.client = _FakeModbusClient(default=_FakeRegistersResult([0, 0]))
    reader.read_all()
    assert reader.all_reads_failed is False
