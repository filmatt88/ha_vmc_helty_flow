"""Unit tests for EASC-001: config schema validation (easc_schema.py)."""

import pytest
import voluptuous as vol

from custom_components.vmc_helty_flow.const import (
    CONF_EASC_ABSOLUTE_HUMIDITY,
    CONF_EASC_ADVANCED_SENSORS,
    CONF_EASC_COMFORT_INDEX,
    CONF_EASC_DEW_POINT,
    CONF_EASC_DEW_POINT_DELTA,
    CONF_EASC_ENABLED,
    CONF_EASC_FORMULA,
    CONF_EASC_HUMIDITY_SOURCE,
    CONF_EASC_TEMPERATURE_EXTERNAL,
    CONF_EASC_TEMPERATURE_INTERNAL,
    CONF_EASC_TEMPERATURE_SOURCE,
    EASC_FORMULA_CUSTOM,
    EASC_FORMULA_MAGNUS,
    EASC_SOURCE_VMC,
)
from custom_components.vmc_helty_flow.easc_schema import (
    EASC_BASE_SENSOR_SCHEMA,
    EASC_CONFIG_SCHEMA,
    EASC_DEW_POINT_DELTA_SCHEMA,
    get_sensor_config,
    is_sensor_enabled,
    validate_easc_config,
    validate_formula,
    validate_source,
)

# ---------------------------------------------------------------------------
# validate_source
# ---------------------------------------------------------------------------


class TestValidateSource:
    """Tests for the validate_source validator."""

    def test_vmc_sentinel_accepted(self):
        assert validate_source(EASC_SOURCE_VMC) == EASC_SOURCE_VMC

    def test_valid_entity_id_accepted(self):
        assert validate_source("sensor.living_room_temp") == "sensor.living_room_temp"

    def test_entity_id_with_digits_accepted(self):
        assert validate_source("sensor.temp_01") == "sensor.temp_01"

    def test_weather_entity_accepted(self):
        assert validate_source("weather.home") == "weather.home"

    def test_empty_string_rejected(self):
        with pytest.raises(vol.Invalid):
            validate_source("")

    def test_none_rejected(self):
        with pytest.raises(vol.Invalid):
            validate_source(None)

    def test_integer_rejected(self):
        with pytest.raises(vol.Invalid):
            validate_source(42)

    def test_missing_dot_rejected(self):
        with pytest.raises(vol.Invalid):
            validate_source("sensor_living_room_temp")

    def test_uppercase_domain_rejected(self):
        with pytest.raises(vol.Invalid):
            validate_source("Sensor.living_room_temp")

    def test_uppercase_object_id_rejected(self):
        with pytest.raises(vol.Invalid):
            validate_source("sensor.LivingRoom")

    def test_spaces_rejected(self):
        with pytest.raises(vol.Invalid):
            validate_source("sensor.living room")

    def test_multiple_dots_rejected(self):
        with pytest.raises(vol.Invalid):
            validate_source("sensor.room.temp")


# ---------------------------------------------------------------------------
# validate_formula
# ---------------------------------------------------------------------------


class TestValidateFormula:
    """Tests for the validate_formula validator."""

    def test_magnus_accepted(self):
        assert validate_formula(EASC_FORMULA_MAGNUS) == EASC_FORMULA_MAGNUS

    def test_custom_accepted(self):
        assert validate_formula(EASC_FORMULA_CUSTOM) == EASC_FORMULA_CUSTOM

    def test_unknown_formula_rejected(self):
        with pytest.raises(vol.Invalid):
            validate_formula("unknown_formula")

    def test_empty_string_rejected(self):
        with pytest.raises(vol.Invalid):
            validate_formula("")

    def test_none_rejected(self):
        with pytest.raises(vol.Invalid):
            validate_formula(None)


# ---------------------------------------------------------------------------
# EASC_BASE_SENSOR_SCHEMA
# ---------------------------------------------------------------------------


class TestBaseSensorSchema:
    """Tests for the base sensor schema (AbsoluteHumidity, DewPoint, ComfortIndex)."""

    def test_empty_dict_uses_defaults(self):
        result = EASC_BASE_SENSOR_SCHEMA({})
        assert result[CONF_EASC_ENABLED] is False
        assert result[CONF_EASC_TEMPERATURE_SOURCE] == EASC_SOURCE_VMC
        assert result[CONF_EASC_HUMIDITY_SOURCE] == EASC_SOURCE_VMC
        assert result[CONF_EASC_FORMULA] == EASC_FORMULA_MAGNUS

    def test_enabled_true_accepted(self):
        result = EASC_BASE_SENSOR_SCHEMA({CONF_EASC_ENABLED: True})
        assert result[CONF_EASC_ENABLED] is True

    def test_external_temperature_source_accepted(self):
        result = EASC_BASE_SENSOR_SCHEMA(
            {CONF_EASC_TEMPERATURE_SOURCE: "sensor.outdoor_temp"}
        )
        assert result[CONF_EASC_TEMPERATURE_SOURCE] == "sensor.outdoor_temp"

    def test_external_humidity_source_accepted(self):
        result = EASC_BASE_SENSOR_SCHEMA(
            {CONF_EASC_HUMIDITY_SOURCE: "sensor.living_room_humidity"}
        )
        assert result[CONF_EASC_HUMIDITY_SOURCE] == "sensor.living_room_humidity"

    def test_custom_formula_accepted(self):
        result = EASC_BASE_SENSOR_SCHEMA({CONF_EASC_FORMULA: EASC_FORMULA_CUSTOM})
        assert result[CONF_EASC_FORMULA] == EASC_FORMULA_CUSTOM

    def test_invalid_entity_id_rejected(self):
        with pytest.raises(vol.Invalid):
            EASC_BASE_SENSOR_SCHEMA({CONF_EASC_TEMPERATURE_SOURCE: "not_an_entity"})

    def test_invalid_formula_rejected(self):
        with pytest.raises(vol.Invalid):
            EASC_BASE_SENSOR_SCHEMA({CONF_EASC_FORMULA: "unknown"})

    def test_full_valid_config(self):
        result = EASC_BASE_SENSOR_SCHEMA(
            {
                CONF_EASC_ENABLED: True,
                CONF_EASC_TEMPERATURE_SOURCE: "sensor.room_temp",
                CONF_EASC_HUMIDITY_SOURCE: "sensor.room_humidity",
                CONF_EASC_FORMULA: EASC_FORMULA_MAGNUS,
            }
        )
        assert result[CONF_EASC_ENABLED] is True
        assert result[CONF_EASC_TEMPERATURE_SOURCE] == "sensor.room_temp"
        assert result[CONF_EASC_HUMIDITY_SOURCE] == "sensor.room_humidity"


# ---------------------------------------------------------------------------
# EASC_DEW_POINT_DELTA_SCHEMA
# ---------------------------------------------------------------------------


class TestDewPointDeltaSchema:
    """Tests for the DewPointDelta sensor schema."""

    def test_empty_dict_uses_defaults(self):
        result = EASC_DEW_POINT_DELTA_SCHEMA({})
        assert result[CONF_EASC_ENABLED] is False
        assert result[CONF_EASC_TEMPERATURE_INTERNAL] == EASC_SOURCE_VMC
        assert result[CONF_EASC_TEMPERATURE_EXTERNAL] == EASC_SOURCE_VMC
        assert result[CONF_EASC_HUMIDITY_SOURCE] == EASC_SOURCE_VMC
        assert result[CONF_EASC_FORMULA] == EASC_FORMULA_MAGNUS

    def test_external_temp_sources_accepted(self):
        result = EASC_DEW_POINT_DELTA_SCHEMA(
            {
                CONF_EASC_TEMPERATURE_INTERNAL: "sensor.indoor_temp",
                CONF_EASC_TEMPERATURE_EXTERNAL: "weather.home",
            }
        )
        assert result[CONF_EASC_TEMPERATURE_INTERNAL] == "sensor.indoor_temp"
        assert result[CONF_EASC_TEMPERATURE_EXTERNAL] == "weather.home"

    def test_invalid_internal_temp_rejected(self):
        with pytest.raises(vol.Invalid):
            EASC_DEW_POINT_DELTA_SCHEMA(
                {CONF_EASC_TEMPERATURE_INTERNAL: "InvalidEntity"}
            )

    def test_does_not_accept_temperature_source_key(self):
        """DewPointDelta uses internal/external keys, not generic temperature_source."""
        with pytest.raises(vol.Invalid):
            EASC_DEW_POINT_DELTA_SCHEMA({CONF_EASC_TEMPERATURE_SOURCE: "sensor.temp"})


# ---------------------------------------------------------------------------
# EASC_CONFIG_SCHEMA (top-level)  # noqa: ERA001
# ---------------------------------------------------------------------------


class TestEascConfigSchema:
    """Tests for the top-level EASC config schema."""

    def test_empty_dict_produces_nested_defaults(self):
        result = EASC_CONFIG_SCHEMA({})
        sensors = result[CONF_EASC_ADVANCED_SENSORS]
        for key in (
            CONF_EASC_ABSOLUTE_HUMIDITY,
            CONF_EASC_DEW_POINT,
            CONF_EASC_COMFORT_INDEX,
            CONF_EASC_DEW_POINT_DELTA,
        ):
            assert key in sensors

    def test_full_valid_config_accepted(self):
        raw = {
            CONF_EASC_ADVANCED_SENSORS: {
                CONF_EASC_ABSOLUTE_HUMIDITY: {
                    CONF_EASC_ENABLED: True,
                    CONF_EASC_TEMPERATURE_SOURCE: "sensor.room_temp",
                    CONF_EASC_HUMIDITY_SOURCE: "sensor.room_humidity",
                },
                CONF_EASC_DEW_POINT: {CONF_EASC_ENABLED: False},
                CONF_EASC_COMFORT_INDEX: {},
                CONF_EASC_DEW_POINT_DELTA: {
                    CONF_EASC_ENABLED: True,
                    CONF_EASC_TEMPERATURE_INTERNAL: "sensor.indoor_temp",
                    CONF_EASC_TEMPERATURE_EXTERNAL: "weather.home",
                    CONF_EASC_HUMIDITY_SOURCE: "sensor.room_humidity",
                },
            }
        }
        result = EASC_CONFIG_SCHEMA(raw)
        abs_hum = result[CONF_EASC_ADVANCED_SENSORS][CONF_EASC_ABSOLUTE_HUMIDITY]
        assert abs_hum[CONF_EASC_ENABLED] is True
        assert abs_hum[CONF_EASC_TEMPERATURE_SOURCE] == "sensor.room_temp"

    def test_invalid_entity_in_nested_sensor_rejected(self):
        with pytest.raises(vol.Invalid):
            EASC_CONFIG_SCHEMA(
                {
                    CONF_EASC_ADVANCED_SENSORS: {
                        CONF_EASC_DEW_POINT: {
                            CONF_EASC_TEMPERATURE_SOURCE: "INVALID_ENTITY"
                        }
                    }
                }
            )


# ---------------------------------------------------------------------------
# validate_easc_config helper
# ---------------------------------------------------------------------------


class TestValidateEascConfig:
    """Tests for the validate_easc_config convenience function."""

    def test_none_returns_defaults(self):
        result = validate_easc_config(None)
        assert CONF_EASC_ADVANCED_SENSORS in result

    def test_empty_dict_returns_defaults(self):
        result = validate_easc_config({})
        assert CONF_EASC_ADVANCED_SENSORS in result

    def test_valid_config_passes_through(self):
        raw = {
            CONF_EASC_ADVANCED_SENSORS: {
                CONF_EASC_COMFORT_INDEX: {CONF_EASC_ENABLED: True}
            }
        }
        result = validate_easc_config(raw)
        comfort = result[CONF_EASC_ADVANCED_SENSORS][CONF_EASC_COMFORT_INDEX]
        assert comfort[CONF_EASC_ENABLED] is True

    def test_invalid_config_raises(self):
        with pytest.raises(vol.Invalid):
            validate_easc_config(
                {
                    CONF_EASC_ADVANCED_SENSORS: {
                        CONF_EASC_DEW_POINT: {CONF_EASC_FORMULA: "not_a_formula"}
                    }
                }
            )


# ---------------------------------------------------------------------------
# get_sensor_config / is_sensor_enabled helpers
# ---------------------------------------------------------------------------


class TestHelpers:
    """Tests for the get_sensor_config and is_sensor_enabled helpers."""

    def _base_config(self):
        return validate_easc_config(
            {
                CONF_EASC_ADVANCED_SENSORS: {
                    CONF_EASC_ABSOLUTE_HUMIDITY: {CONF_EASC_ENABLED: True},
                    CONF_EASC_DEW_POINT: {CONF_EASC_ENABLED: False},
                }
            }
        )

    def test_get_sensor_config_returns_dict(self):
        cfg = self._base_config()
        result = get_sensor_config(cfg, CONF_EASC_ABSOLUTE_HUMIDITY)
        assert isinstance(result, dict)
        assert result[CONF_EASC_ENABLED] is True

    def test_get_sensor_config_missing_key_returns_empty_dict(self):
        # All sensors have defaults, but test with a completely empty sensors map
        result = get_sensor_config(
            {CONF_EASC_ADVANCED_SENSORS: {}}, CONF_EASC_COMFORT_INDEX
        )
        assert result == {}

    def test_is_sensor_enabled_true(self):
        cfg = self._base_config()
        assert is_sensor_enabled(cfg, CONF_EASC_ABSOLUTE_HUMIDITY) is True

    def test_is_sensor_enabled_false(self):
        cfg = self._base_config()
        assert is_sensor_enabled(cfg, CONF_EASC_DEW_POINT) is False

    def test_is_sensor_enabled_missing_key_returns_false(self):
        assert (
            is_sensor_enabled({CONF_EASC_ADVANCED_SENSORS: {}}, CONF_EASC_COMFORT_INDEX)
            is False
        )
