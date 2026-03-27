"""EASC — External Advanced Sensor Configuration: schema and validators.

Defines the voluptuous schema used to validate the ``easc_config`` section
stored in ``config_entry.options``.  The schema is kept in a dedicated module
so it can be imported by both the config-flow (EASC-003) and unit tests
without pulling in the full Home Assistant runtime.

Structure stored in options::

    {
        "easc_config": {
            "advanced_sensors": {
                "absolute_humidity":  { <EASCBaseSensorSchema> },
                "dew_point":          { <EASCBaseSensorSchema> },
                "comfort_index":      { <EASCBaseSensorSchema> },
                "dew_point_delta":    { <EASCDewPointDeltaSchema> },
            }
        }
    }
"""

from __future__ import annotations

import re

import voluptuous as vol

from .const import (
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
    EASC_FORMULA_MAGNUS,
    EASC_SOURCE_VMC,
    EASC_VALID_FORMULAS,
)

# ---------------------------------------------------------------------------
# Regex for a valid Home Assistant entity_id  (domain.object_id)
# domain    : lowercase letters and underscores
# object_id : lowercase letters, digits and underscores
# ---------------------------------------------------------------------------
_ENTITY_ID_RE = re.compile(r"^[a-z_]+\.[a-z0-9_]+$")


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def validate_source(value: object) -> str:
    """Accept either the sentinel ``"vmc"`` or a well-formed HA entity_id.

    Raises:
        vol.Invalid: when the value is not a non-empty string, is not the
            ``"vmc"`` sentinel, and does not match the entity_id pattern.
    """
    if not isinstance(value, str) or not value:
        raise vol.Invalid("Source must be a non-empty string")
    if value == EASC_SOURCE_VMC:
        return value
    if not _ENTITY_ID_RE.match(value):
        raise vol.Invalid(
            f"Invalid entity_id '{value}': expected '<domain>.<object_id>' "
            f"(e.g. 'sensor.living_room_temp') or '{EASC_SOURCE_VMC}'"
        )
    return value


def validate_formula(value: object) -> str:
    """Accept only known formula identifiers.

    Raises:
        vol.Invalid: when the value is not in :data:`EASC_VALID_FORMULAS`.
    """
    if value not in EASC_VALID_FORMULAS:
        raise vol.Invalid(
            f"Formula '{value}' is not supported. "
            f"Valid options: {EASC_VALID_FORMULAS}"
        )
    return value  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Per-sensor schemas
# ---------------------------------------------------------------------------

#: Schema for sensors that need temperature + humidity sources
#: (AbsoluteHumidity, DewPoint, ComfortIndex)
EASC_BASE_SENSOR_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_EASC_ENABLED, default=False): bool,
        vol.Optional(
            CONF_EASC_TEMPERATURE_SOURCE, default=EASC_SOURCE_VMC
        ): validate_source,
        vol.Optional(
            CONF_EASC_HUMIDITY_SOURCE, default=EASC_SOURCE_VMC
        ): validate_source,
        vol.Optional(CONF_EASC_FORMULA, default=EASC_FORMULA_MAGNUS): validate_formula,
    }
)

#: Schema for DewPointDelta which requires separate internal/external temp
EASC_DEW_POINT_DELTA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_EASC_ENABLED, default=False): bool,
        vol.Optional(
            CONF_EASC_TEMPERATURE_INTERNAL, default=EASC_SOURCE_VMC
        ): validate_source,
        vol.Optional(
            CONF_EASC_TEMPERATURE_EXTERNAL, default=EASC_SOURCE_VMC
        ): validate_source,
        vol.Optional(
            CONF_EASC_HUMIDITY_SOURCE, default=EASC_SOURCE_VMC
        ): validate_source,
        vol.Optional(CONF_EASC_FORMULA, default=EASC_FORMULA_MAGNUS): validate_formula,
    }
)

#: Schema for the ``advanced_sensors`` mapping
EASC_ADVANCED_SENSORS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_EASC_ABSOLUTE_HUMIDITY, default={}): EASC_BASE_SENSOR_SCHEMA,
        vol.Optional(CONF_EASC_DEW_POINT, default={}): EASC_BASE_SENSOR_SCHEMA,
        vol.Optional(CONF_EASC_COMFORT_INDEX, default={}): EASC_BASE_SENSOR_SCHEMA,
        vol.Optional(
            CONF_EASC_DEW_POINT_DELTA, default={}
        ): EASC_DEW_POINT_DELTA_SCHEMA,
    }
)

#: Top-level EASC config schema (stored under ``options["easc_config"]``)
EASC_CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONF_EASC_ADVANCED_SENSORS, default={}
        ): EASC_ADVANCED_SENSORS_SCHEMA,
    }
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def validate_easc_config(raw: object) -> dict:
    """Validate and normalise a raw EASC config dict.

    Args:
        raw: The ``options["easc_config"]`` value coming from config-entry
            storage or user input.  ``None`` and ``{}`` are both accepted and
            produce a fully-defaulted config.

    Returns:
        A validated dict conforming to :data:`EASC_CONFIG_SCHEMA`.

    Raises:
        vol.Invalid: on validation failure.
    """
    result: dict = EASC_CONFIG_SCHEMA(raw or {})
    return result


def get_sensor_config(easc_config: dict, sensor_key: str) -> dict:
    """Return the validated config for a single advanced sensor.

    Args:
        easc_config: A dict previously validated by :func:`validate_easc_config`.
        sensor_key: One of the ``CONF_EASC_*`` sensor identifier constants.

    Returns:
        The sensor sub-dict (always a dict, never ``None``).
    """
    sensors = easc_config.get(CONF_EASC_ADVANCED_SENSORS, {})
    result: dict = sensors.get(sensor_key, {})
    return result


def is_sensor_enabled(easc_config: dict, sensor_key: str) -> bool:
    """Return ``True`` if the given advanced sensor has EASC enabled."""
    return bool(
        get_sensor_config(easc_config, sensor_key).get(CONF_EASC_ENABLED, False)
    )
