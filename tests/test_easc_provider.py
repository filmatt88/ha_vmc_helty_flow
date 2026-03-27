"""Unit tests for EASC-002 / TEST-004: EASCDataProvider (easc_provider.py).

Covers:
- magnus_coefficients: Magnus-Tetens vs August-Roche-Magnus
- celsius_from_unit: °C, °F, unknown units
- humidity_to_percent: %, 0-1 fraction, unitless large values
- get_entity_state: present / unavailable / unknown / missing
- get_temperature / get_temperature_external: VMC source, entity source,
  °F conversion, fallback to VMC, warning log
- get_humidity: VMC source, entity source, fraction normalisation,
  fallback to VMC, warning log
- Mixed scenarios: VMC source bypasses hass, entity overrides VMC,
  double fallback returns None
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from custom_components.vmc_helty_flow.const import (
    EASC_FORMULA_CUSTOM,
    EASC_FORMULA_MAGNUS,
    EASC_SOURCE_VMC,
)
from custom_components.vmc_helty_flow.easc_provider import (
    EASCDataProvider,
    celsius_from_unit,
    humidity_to_percent,
    magnus_coefficients,
)

# ---------------------------------------------------------------------------
# Helpers — minimal stubs for hass and coordinator
# ---------------------------------------------------------------------------

_VMGI_TEMPLATE = "VMGI,{t_int},{t_ext},{hum},400,0,0,0,0,0,0,0,0,0,0"


def _make_coordinator(t_int=215, t_ext=80, hum=550):
    """Return a coordinator stub with a VMGI response.

    Default values:
        t_int = 215  → 21.5 °C internal temperature
        t_ext = 80   →  8.0 °C external temperature
        hum   = 550  → 55.0 % humidity
    """
    coordinator = MagicMock()
    coordinator.data = {
        "sensors": _VMGI_TEMPLATE.format(t_int=t_int, t_ext=t_ext, hum=hum)
    }
    return coordinator


def _make_state(state_value: str, unit: str | None = None):
    """Return a minimal HA state stub."""
    attrs = {}
    if unit is not None:
        attrs["unit_of_measurement"] = unit
    return SimpleNamespace(state=state_value, attributes=attrs)


def _make_hass(entities: dict[str, SimpleNamespace] | None = None):
    """Return a minimal hass stub with a states registry."""
    hass = MagicMock()
    store = entities or {}
    hass.states.get.side_effect = store.get
    return hass


# ---------------------------------------------------------------------------
# magnus_coefficients
# ---------------------------------------------------------------------------


class TestMagnusCoefficients:
    def test_magnus_formula_returns_tetens_coefficients(self):
        a, b = magnus_coefficients(EASC_FORMULA_MAGNUS)
        assert a == pytest.approx(17.27)
        assert b == pytest.approx(237.7)

    def test_custom_formula_returns_arm_coefficients(self):
        a, b = magnus_coefficients(EASC_FORMULA_CUSTOM)
        assert a == pytest.approx(17.625)
        assert b == pytest.approx(243.04)

    def test_unknown_formula_defaults_to_magnus_tetens(self):
        a, b = magnus_coefficients("unknown_formula")
        assert a == pytest.approx(17.27)
        assert b == pytest.approx(237.7)

    def test_returns_tuple_of_two_floats(self):
        result = magnus_coefficients(EASC_FORMULA_MAGNUS)
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert all(isinstance(v, float) for v in result)

    def test_custom_more_accurate_for_wmo_range(self):
        """ARM (custom) coefficients differ from Magnus-Tetens coefficients."""
        a_m, b_m = magnus_coefficients(EASC_FORMULA_MAGNUS)
        a_c, b_c = magnus_coefficients(EASC_FORMULA_CUSTOM)
        # Coefficients are different between the two formulas
        assert (a_m, b_m) != (a_c, b_c)


# ---------------------------------------------------------------------------
# celsius_from_unit
# ---------------------------------------------------------------------------


class TestCelsiusFromUnit:
    def test_celsius_unit_unchanged(self):
        assert celsius_from_unit(21.5, "°C") == pytest.approx(21.5)

    def test_none_unit_unchanged(self):
        assert celsius_from_unit(21.5, None) == pytest.approx(21.5)

    def test_fahrenheit_symbol_converted(self):
        assert celsius_from_unit(32.0, "°F") == pytest.approx(0.0)

    def test_fahrenheit_letter_converted(self):
        assert celsius_from_unit(212.0, "F") == pytest.approx(100.0)

    def test_body_temperature_conversion(self):
        assert celsius_from_unit(98.6, "°F") == pytest.approx(37.0, abs=0.01)

    def test_negative_fahrenheit(self):
        assert celsius_from_unit(-40.0, "°F") == pytest.approx(-40.0)

    def test_unknown_unit_unchanged(self):
        assert celsius_from_unit(25.0, "K") == pytest.approx(25.0)


# ---------------------------------------------------------------------------
# humidity_to_percent
# ---------------------------------------------------------------------------


class TestHumidityToPercent:
    def test_percent_unit_unchanged(self):
        assert humidity_to_percent(55.0, "%") == pytest.approx(55.0)

    def test_none_unit_fraction_converted(self):
        assert humidity_to_percent(0.55, None) == pytest.approx(55.0)

    def test_none_unit_zero_converted(self):
        assert humidity_to_percent(0.0, None) == pytest.approx(0.0)

    def test_none_unit_one_converted(self):
        assert humidity_to_percent(1.0, None) == pytest.approx(100.0)

    def test_none_unit_above_one_unchanged(self):
        # value > 1 without unit → already percent
        assert humidity_to_percent(55.0, None) == pytest.approx(55.0)

    def test_unknown_unit_unchanged(self):
        assert humidity_to_percent(55.0, "g/kg") == pytest.approx(55.0)


# ---------------------------------------------------------------------------
# get_entity_state
# ---------------------------------------------------------------------------


class TestGetEntityState:
    def test_returns_state_for_existing_entity(self):
        hass = _make_hass({"sensor.temp": _make_state("22.5")})
        provider = EASCDataProvider(hass, _make_coordinator())
        assert provider.get_entity_state("sensor.temp") == "22.5"

    def test_returns_none_for_missing_entity(self):
        hass = _make_hass()
        provider = EASCDataProvider(hass, _make_coordinator())
        assert provider.get_entity_state("sensor.missing") is None

    def test_returns_none_for_unavailable(self):
        hass = _make_hass({"sensor.x": _make_state("unavailable")})
        provider = EASCDataProvider(hass, _make_coordinator())
        assert provider.get_entity_state("sensor.x") is None

    def test_returns_none_for_unknown(self):
        hass = _make_hass({"sensor.x": _make_state("unknown")})
        provider = EASCDataProvider(hass, _make_coordinator())
        assert provider.get_entity_state("sensor.x") is None


# ---------------------------------------------------------------------------
# get_temperature — VMC source
# ---------------------------------------------------------------------------


class TestGetTemperatureVmc:
    def test_reads_internal_temp_from_vmgi(self):
        provider = EASCDataProvider(_make_hass(), _make_coordinator(t_int=215))
        assert provider.get_temperature(EASC_SOURCE_VMC) == pytest.approx(21.5)

    def test_returns_none_when_no_coordinator_data(self):
        coordinator = MagicMock()
        coordinator.data = None
        provider = EASCDataProvider(_make_hass(), coordinator)
        assert provider.get_temperature(EASC_SOURCE_VMC) is None

    def test_returns_none_for_malformed_vmgi(self):
        coordinator = MagicMock()
        coordinator.data = {"sensors": "VMGI,bad"}
        provider = EASCDataProvider(_make_hass(), coordinator)
        assert provider.get_temperature(EASC_SOURCE_VMC) is None

    def test_returns_none_for_non_vmgi_response(self):
        coordinator = MagicMock()
        coordinator.data = {"sensors": "VMGO,1,0,215,550,1000"}
        provider = EASCDataProvider(_make_hass(), coordinator)
        assert provider.get_temperature(EASC_SOURCE_VMC) is None


# ---------------------------------------------------------------------------
# get_temperature — external entity source
# ---------------------------------------------------------------------------


class TestGetTemperatureEntity:
    def test_reads_celsius_entity(self):
        hass = _make_hass({"sensor.room": _make_state("22.3", "°C")})
        provider = EASCDataProvider(hass, _make_coordinator())
        assert provider.get_temperature("sensor.room") == pytest.approx(22.3)

    def test_converts_fahrenheit_entity(self):
        hass = _make_hass({"sensor.room": _make_state("72.0", "°F")})
        provider = EASCDataProvider(hass, _make_coordinator())
        # 72 °F → 22.22 °C
        assert provider.get_temperature("sensor.room") == pytest.approx(22.22, abs=0.01)

    def test_falls_back_to_vmc_when_entity_missing(self):
        hass = _make_hass()  # no entities
        provider = EASCDataProvider(hass, _make_coordinator(t_int=200))
        assert provider.get_temperature("sensor.missing") == pytest.approx(20.0)

    def test_falls_back_to_vmc_when_entity_unavailable(self):
        hass = _make_hass({"sensor.x": _make_state("unavailable")})
        provider = EASCDataProvider(hass, _make_coordinator(t_int=185))
        assert provider.get_temperature("sensor.x") == pytest.approx(18.5)

    def test_falls_back_to_vmc_when_entity_non_numeric(self):
        hass = _make_hass({"sensor.x": _make_state("n/a")})
        provider = EASCDataProvider(hass, _make_coordinator(t_int=200))
        assert provider.get_temperature("sensor.x") == pytest.approx(20.0)

    def test_fallback_logs_warning(self):
        hass = _make_hass()
        provider = EASCDataProvider(hass, _make_coordinator())
        with patch(
            "custom_components.vmc_helty_flow.easc_provider._LOGGER"
        ) as mock_logger:
            provider.get_temperature("sensor.missing")
            mock_logger.warning.assert_called_once()


# ---------------------------------------------------------------------------
# get_temperature_external
# ---------------------------------------------------------------------------


class TestGetTemperatureExternal:
    def test_reads_vmc_external(self):
        provider = EASCDataProvider(_make_hass(), _make_coordinator(t_ext=80))
        assert provider.get_temperature_external(EASC_SOURCE_VMC) == pytest.approx(8.0)

    def test_reads_external_entity(self):
        hass = _make_hass({"weather.home": _make_state("5.0", "°C")})
        provider = EASCDataProvider(hass, _make_coordinator())
        assert provider.get_temperature_external("weather.home") == pytest.approx(5.0)

    def test_falls_back_to_vmc_external(self):
        hass = _make_hass()  # no entities
        provider = EASCDataProvider(hass, _make_coordinator(t_ext=30))
        assert provider.get_temperature_external("weather.missing") == pytest.approx(
            3.0
        )


# ---------------------------------------------------------------------------
# get_humidity — VMC source
# ---------------------------------------------------------------------------


class TestGetHumidityVmc:
    def test_reads_humidity_from_vmgi(self):
        provider = EASCDataProvider(_make_hass(), _make_coordinator(hum=650))
        assert provider.get_humidity(EASC_SOURCE_VMC) == pytest.approx(65.0)

    def test_returns_none_when_no_coordinator_data(self):
        coordinator = MagicMock()
        coordinator.data = None
        provider = EASCDataProvider(_make_hass(), coordinator)
        assert provider.get_humidity(EASC_SOURCE_VMC) is None


# ---------------------------------------------------------------------------
# get_humidity — external entity source
# ---------------------------------------------------------------------------


class TestGetHumidityEntity:
    def test_reads_percent_entity(self):
        hass = _make_hass({"sensor.hum": _make_state("60.0", "%")})
        provider = EASCDataProvider(hass, _make_coordinator())
        assert provider.get_humidity("sensor.hum") == pytest.approx(60.0)

    def test_normalises_fraction_entity(self):
        hass = _make_hass({"sensor.hum": _make_state("0.60")})  # no unit
        provider = EASCDataProvider(hass, _make_coordinator())
        assert provider.get_humidity("sensor.hum") == pytest.approx(60.0)

    def test_falls_back_to_vmc_when_entity_missing(self):
        hass = _make_hass()
        provider = EASCDataProvider(hass, _make_coordinator(hum=450))
        assert provider.get_humidity("sensor.missing") == pytest.approx(45.0)

    def test_falls_back_to_vmc_when_entity_unavailable(self):
        hass = _make_hass({"sensor.hum": _make_state("unavailable")})
        provider = EASCDataProvider(hass, _make_coordinator(hum=700))
        assert provider.get_humidity("sensor.hum") == pytest.approx(70.0)

    def test_falls_back_logs_warning(self):
        hass = _make_hass()
        provider = EASCDataProvider(hass, _make_coordinator())
        with patch(
            "custom_components.vmc_helty_flow.easc_provider._LOGGER"
        ) as mock_logger:
            provider.get_humidity("sensor.missing")
            mock_logger.warning.assert_called_once()


# ---------------------------------------------------------------------------
# Mixed scenarios
# ---------------------------------------------------------------------------


class TestMixedScenarios:
    def test_vmc_source_never_calls_hass_states(self):
        """When source is 'vmc', hass.states.get should not be called."""
        hass = _make_hass()
        provider = EASCDataProvider(hass, _make_coordinator())
        provider.get_temperature(EASC_SOURCE_VMC)
        provider.get_humidity(EASC_SOURCE_VMC)
        hass.states.get.assert_not_called()

    def test_external_source_returns_entity_value_not_vmc(self):
        """When the external entity is available, its value is returned (not VMC)."""
        hass = _make_hass({"sensor.t": _make_state("25.0", "°C")})
        # VMC internal temp is 21.5 °C - different value to confirm the entity was used
        provider = EASCDataProvider(hass, _make_coordinator(t_int=215))
        result = provider.get_temperature("sensor.t")
        assert result == pytest.approx(25.0)  # entity value, not 21.5 from VMC

    def test_double_fallback_returns_none_when_vmc_also_empty(self):
        """Returns None when both external source and VMC are unavailable."""
        hass = _make_hass()
        coordinator = MagicMock()
        coordinator.data = None
        provider = EASCDataProvider(hass, coordinator)
        assert provider.get_temperature("sensor.missing") is None
        assert provider.get_humidity("sensor.missing") is None
