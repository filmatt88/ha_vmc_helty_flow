"""Unit tests for EASC-003: VmcHeltyOptionsFlowHandler EASC step.

Covers:
- _flatten_easc_config / _build_easc_config_from_input round-trip
- async_step_init: checkbox absent → no EASC step, saves existing config
- async_step_init: checkbox present → redirects to advanced_sensors
- async_step_advanced_sensors: valid input → creates entry
- async_step_advanced_sensors: invalid source → returns errors
- async_step_advanced_sensors: form shown with defaults when GET
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.vmc_helty_flow.config_flow import (
    VmcHeltyOptionsFlowHandler,
    _build_easc_config_from_input,
    _flatten_easc_config,
)
from custom_components.vmc_helty_flow.const import (
    CONF_EASC_ABSOLUTE_HUMIDITY,
    CONF_EASC_CONFIG,
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

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_FLAT = {
    "abs_hum_enabled": True,
    "abs_hum_temperature_source": "sensor.temp",
    "abs_hum_humidity_source": None,  # None = use VMC
    "abs_hum_formula": EASC_FORMULA_MAGNUS,
    "dew_point_enabled": False,
    "dew_point_temperature_source": None,
    "dew_point_humidity_source": None,
    "dew_point_formula": EASC_FORMULA_CUSTOM,
    "comfort_index_enabled": False,
    "comfort_index_temperature_source": None,
    "comfort_index_humidity_source": None,
    "comfort_index_formula": EASC_FORMULA_MAGNUS,
    "dew_point_delta_enabled": True,
    "dew_point_delta_temperature_internal": "sensor.indoor_temp",
    "dew_point_delta_temperature_external": "weather.home",
    "dew_point_delta_humidity_source": None,
    "dew_point_delta_formula": EASC_FORMULA_CUSTOM,
}

_ALL_VMC_FLAT = {
    "abs_hum_enabled": False,
    "abs_hum_temperature_source": None,  # None = use VMC device
    "abs_hum_humidity_source": None,
    "abs_hum_formula": EASC_FORMULA_MAGNUS,
    "dew_point_enabled": False,
    "dew_point_temperature_source": None,
    "dew_point_humidity_source": None,
    "dew_point_formula": EASC_FORMULA_MAGNUS,
    "comfort_index_enabled": False,
    "comfort_index_temperature_source": None,
    "comfort_index_humidity_source": None,
    "comfort_index_formula": EASC_FORMULA_MAGNUS,
    "dew_point_delta_enabled": False,
    "dew_point_delta_temperature_internal": None,
    "dew_point_delta_temperature_external": None,
    "dew_point_delta_humidity_source": None,
    "dew_point_delta_formula": EASC_FORMULA_MAGNUS,
}


def _make_config_entry(options: dict | None = None) -> MagicMock:
    entry = MagicMock()
    entry.options = options or {}
    entry.data = {}
    return entry


def _make_handler(options: dict | None = None) -> VmcHeltyOptionsFlowHandler:
    handler = VmcHeltyOptionsFlowHandler()
    # Use internal attribute to avoid deprecated setter (HA 2025.12+)
    handler._config_entry = _make_config_entry(options)
    handler.hass = MagicMock()
    return handler


def _unwrap(result):
    """Return the result dict from async_show_form or async_create_entry."""
    return result


# ---------------------------------------------------------------------------
# _flatten_easc_config
# ---------------------------------------------------------------------------


class TestFlattenEascConfig:
    def test_empty_input_produces_all_vmc_defaults(self):
        flat = _flatten_easc_config({})
        assert flat == _ALL_VMC_FLAT

    def test_none_input_produces_defaults(self):
        flat = _flatten_easc_config(None)
        assert flat == _ALL_VMC_FLAT

    def test_enabled_flag_preserved(self):
        nested = {
            "advanced_sensors": {CONF_EASC_ABSOLUTE_HUMIDITY: {CONF_EASC_ENABLED: True}}
        }
        flat = _flatten_easc_config(nested)
        assert flat["abs_hum_enabled"] is True

    def test_external_source_preserved(self):
        nested = {
            "advanced_sensors": {
                CONF_EASC_DEW_POINT: {CONF_EASC_TEMPERATURE_SOURCE: "sensor.outdoor"}
            }
        }
        flat = _flatten_easc_config(nested)
        assert flat["dew_point_temperature_source"] == "sensor.outdoor"

    def test_dew_point_delta_internal_external_preserved(self):
        nested = {
            "advanced_sensors": {
                CONF_EASC_DEW_POINT_DELTA: {
                    CONF_EASC_TEMPERATURE_INTERNAL: "sensor.in",
                    CONF_EASC_TEMPERATURE_EXTERNAL: "weather.out",
                }
            }
        }
        flat = _flatten_easc_config(nested)
        assert flat["dew_point_delta_temperature_internal"] == "sensor.in"
        assert flat["dew_point_delta_temperature_external"] == "weather.out"

    def test_has_exactly_17_keys(self):
        flat = _flatten_easc_config({})
        assert len(flat) == 17


# ---------------------------------------------------------------------------
# _build_easc_config_from_input
# ---------------------------------------------------------------------------


class TestBuildEascConfigFromInput:
    def test_round_trip_all_vmc(self):
        nested = _build_easc_config_from_input(_ALL_VMC_FLAT)
        assert (
            nested["advanced_sensors"][CONF_EASC_ABSOLUTE_HUMIDITY][CONF_EASC_ENABLED]
            is False
        )
        assert (
            nested["advanced_sensors"][CONF_EASC_ABSOLUTE_HUMIDITY][
                CONF_EASC_TEMPERATURE_SOURCE
            ]
            == EASC_SOURCE_VMC
        )

    def test_round_trip_with_entities(self):
        nested = _build_easc_config_from_input(_VALID_FLAT)
        ah = nested["advanced_sensors"][CONF_EASC_ABSOLUTE_HUMIDITY]
        assert ah[CONF_EASC_ENABLED] is True
        assert ah[CONF_EASC_TEMPERATURE_SOURCE] == "sensor.temp"
        dpd = nested["advanced_sensors"][CONF_EASC_DEW_POINT_DELTA]
        assert dpd[CONF_EASC_TEMPERATURE_INTERNAL] == "sensor.indoor_temp"
        assert dpd[CONF_EASC_TEMPERATURE_EXTERNAL] == "weather.home"

    def test_flatten_build_idempotent(self):
        """flatten → build → flatten should give the same flat dict."""
        nested1 = _build_easc_config_from_input(_VALID_FLAT)
        flat2 = _flatten_easc_config(nested1)
        assert flat2 == _VALID_FLAT


# ---------------------------------------------------------------------------
# async_step_init — no EASC checkbox
# ---------------------------------------------------------------------------


class TestOptionsStepInit:
    @pytest.mark.asyncio
    async def test_get_shows_form(self):
        handler = _make_handler()
        result = await handler.async_step_init(None)
        assert result["type"] == "form"
        assert result["step_id"] == "init"

    @pytest.mark.asyncio
    async def test_submit_without_easc_creates_entry(self):
        existing_easc = {"advanced_sensors": {}}
        handler = _make_handler(
            options={
                "room_volume": 50.0,
                "scan_interval": 60,
                "timeout": 10,
                "retry_attempts": 3,
                CONF_EASC_CONFIG: existing_easc,
            }
        )
        user_input = {
            "room_volume": 55.0,
            "scan_interval": 120,
            "timeout": 15,
            "retry_attempts": 2,
            "configure_easc": False,
        }
        result = await handler.async_step_init(user_input)
        assert result["type"] == "create_entry"
        assert result["data"]["room_volume"] == 55.0
        # configure_easc must be stripped
        assert "configure_easc" not in result["data"]
        # Existing EASC config is carried forward unchanged
        assert result["data"][CONF_EASC_CONFIG] == existing_easc

    @pytest.mark.asyncio
    async def test_submit_with_configure_easc_redirects_to_step2(self):
        handler = _make_handler()
        user_input = {
            "room_volume": 50.0,
            "scan_interval": 60,
            "timeout": 10,
            "retry_attempts": 3,
            "configure_easc": True,
        }
        result = await handler.async_step_init(user_input)
        # Should show advanced_sensors form
        assert result["type"] == "form"
        assert result["step_id"] == "advanced_sensors"

    @pytest.mark.asyncio
    async def test_base_options_stored_for_step2(self):
        handler = _make_handler()
        user_input = {
            "room_volume": 42.0,
            "scan_interval": 90,
            "timeout": 20,
            "retry_attempts": 5,
            "configure_easc": True,
        }
        await handler.async_step_init(user_input)
        assert handler._base_options["room_volume"] == 42.0
        assert "configure_easc" not in handler._base_options


# ---------------------------------------------------------------------------
# async_step_advanced_sensors
# ---------------------------------------------------------------------------


class TestOptionsStepAdvancedSensors:
    @pytest.mark.asyncio
    async def test_get_shows_form_with_defaults(self):
        handler = _make_handler()
        result = await handler.async_step_advanced_sensors(None)
        assert result["type"] == "form"
        assert result["step_id"] == "advanced_sensors"

    @pytest.mark.asyncio
    async def test_valid_input_creates_entry(self):
        handler = _make_handler()
        handler._base_options = {
            "room_volume": 50.0,
            "scan_interval": 60,
            "timeout": 10,
            "retry_attempts": 3,
        }
        result = await handler.async_step_advanced_sensors(_VALID_FLAT)
        assert result["type"] == "create_entry"
        assert CONF_EASC_CONFIG in result["data"]
        ah = result["data"][CONF_EASC_CONFIG]["advanced_sensors"][
            CONF_EASC_ABSOLUTE_HUMIDITY
        ]
        assert ah[CONF_EASC_ENABLED] is True
        assert ah[CONF_EASC_TEMPERATURE_SOURCE] == "sensor.temp"

    @pytest.mark.asyncio
    async def test_base_options_merged_into_final_entry(self):
        handler = _make_handler()
        handler._base_options = {"room_volume": 77.0, "scan_interval": 120}
        result = await handler.async_step_advanced_sensors(_ALL_VMC_FLAT)
        assert result["data"]["room_volume"] == 77.0
        assert result["data"]["scan_interval"] == 120

    @pytest.mark.asyncio
    async def test_invalid_source_returns_error(self):
        handler = _make_handler()
        handler._base_options = {}
        bad_input = dict(_ALL_VMC_FLAT)
        bad_input["abs_hum_temperature_source"] = "INVALID_ENTITY"
        result = await handler.async_step_advanced_sensors(bad_input)
        assert result["type"] == "form"
        assert "abs_hum_temperature_source" in result["errors"]

    @pytest.mark.asyncio
    async def test_multiple_invalid_sources_all_reported(self):
        handler = _make_handler()
        handler._base_options = {}
        bad_input = dict(_ALL_VMC_FLAT)
        bad_input["abs_hum_temperature_source"] = "BAD1"
        bad_input["dew_point_humidity_source"] = "BAD2"
        result = await handler.async_step_advanced_sensors(bad_input)
        assert "abs_hum_temperature_source" in result["errors"]
        assert "dew_point_humidity_source" in result["errors"]

    @pytest.mark.asyncio
    async def test_vmc_sentinel_always_valid(self):
        handler = _make_handler()
        handler._base_options = {}
        result = await handler.async_step_advanced_sensors(_ALL_VMC_FLAT)
        assert result["type"] == "create_entry"
        assert not result.get("errors")

    @pytest.mark.asyncio
    async def test_existing_easc_config_prefills_defaults(self):
        existing = {
            "advanced_sensors": {
                CONF_EASC_ABSOLUTE_HUMIDITY: {
                    CONF_EASC_ENABLED: True,
                    CONF_EASC_TEMPERATURE_SOURCE: "sensor.existing",
                    CONF_EASC_HUMIDITY_SOURCE: EASC_SOURCE_VMC,
                }
            }
        }
        handler = _make_handler(options={CONF_EASC_CONFIG: existing})
        # GET request (no user_input) — form shown with existing defaults baked in
        result = await handler.async_step_advanced_sensors(None)
        assert result["type"] == "form"
        schema = result["data_schema"]
        # Check the schema default for abs_hum_temperature_source
        defaults = {
            k.schema: k.default() for k in schema.schema if hasattr(k, "default")
        }
        assert defaults.get("abs_hum_temperature_source") == "sensor.existing"
        assert defaults.get("abs_hum_enabled") is True

    @pytest.mark.asyncio
    async def test_custom_formula_accepted(self):
        handler = _make_handler()
        handler._base_options = {}
        custom_flat = dict(_ALL_VMC_FLAT)
        custom_flat["dew_point_formula"] = EASC_FORMULA_CUSTOM
        result = await handler.async_step_advanced_sensors(custom_flat)
        assert result["type"] == "create_entry"
        dp = result["data"][CONF_EASC_CONFIG]["advanced_sensors"][CONF_EASC_DEW_POINT]
        assert dp[CONF_EASC_FORMULA] == EASC_FORMULA_CUSTOM

    @pytest.mark.asyncio
    async def test_invalid_formula_returns_error(self):
        handler = _make_handler()
        handler._base_options = {}
        bad_input = dict(_ALL_VMC_FLAT)
        bad_input["abs_hum_formula"] = "invalid_formula"
        result = await handler.async_step_advanced_sensors(bad_input)
        assert result["type"] == "form"
        assert "abs_hum_formula" in result["errors"]

    def test_formula_preserved_in_flatten(self):
        nested = {
            "advanced_sensors": {
                CONF_EASC_DEW_POINT: {CONF_EASC_FORMULA: EASC_FORMULA_CUSTOM}
            }
        }
        flat = _flatten_easc_config(nested)
        assert flat["dew_point_formula"] == EASC_FORMULA_CUSTOM

    def test_formula_in_build_output(self):
        flat = dict(_ALL_VMC_FLAT)
        flat["abs_hum_formula"] = EASC_FORMULA_CUSTOM
        nested = _build_easc_config_from_input(flat)
        assert (
            nested["advanced_sensors"][CONF_EASC_ABSOLUTE_HUMIDITY][CONF_EASC_FORMULA]
            == EASC_FORMULA_CUSTOM
        )
