"""EASC — External Advanced Sensor Configuration: data provider.

``EASCDataProvider`` is the single point of access for sensor data used by the
advanced calculated sensors (AbsoluteHumidity, DewPoint, ComfortIndex,
DewPointDelta).  For each data point it can read from:

* The VMC device itself (``source == EASC_SOURCE_VMC``, the default).
* Any Home Assistant entity (``source = "domain.object_id"``).

When an external source is configured but unavailable (entity missing,
``unavailable``, ``unknown`` state, or non-numeric value) the provider
automatically falls back to the corresponding VMC value and logs a warning.

Unit conversions handled transparently:
* Temperature: ``°F`` → ``°C`` (all other units assumed to be ``°C``).
* Humidity: ``0-1`` normalised range -> ``0-100 %``.
"""

from __future__ import annotations

import logging

from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant

from .const import (
    EASC_FORMULA_CUSTOM,
    EASC_SOURCE_VMC,
    MIN_RESPONSE_PARTS,
)

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Formula helpers
# ---------------------------------------------------------------------------


def magnus_coefficients(formula: str) -> tuple[float, float]:
    """Return Magnus ``(a, b)`` coefficients for *formula*.

    Args:
        formula: ``"magnus"`` for standard Magnus-Tetens or ``"custom"`` for
                 the August-Roche-Magnus equation (Alduchov & Eskridge 1996).

    Returns:
        ``(a, b)`` tuple used in saturation-vapour-pressure expressions.

    Notes:
        * **Magnus-Tetens** (``"magnus"``): a=17.27, b=237.7.
          General-purpose, accurate from -40 degC to +50 degC.
        * **August-Roche-Magnus** (``"custom"``): a=17.625, b=243.04.
          Recommended by the WMO; more accurate in the 0-60 degC range.
    """
    if formula == EASC_FORMULA_CUSTOM:
        return (17.625, 243.04)
    return (17.27, 237.7)


# ---------------------------------------------------------------------------
# Standalone unit-conversion utilities (pure functions, easy to test)
# ---------------------------------------------------------------------------


def celsius_from_unit(value: float, unit: str | None) -> float:
    """Return *value* converted to °C.

    Args:
        value: Numeric temperature value as reported by the source.
        unit:  ``ATTR_UNIT_OF_MEASUREMENT`` string, or ``None``.

    Returns:
        Temperature in °C.  If *unit* is ``"°F"`` or ``"F"`` the Fahrenheit
        conversion is applied; all other values (including ``None``) are
        treated as Celsius and returned unchanged.
    """
    if unit in ("°F", "F"):
        return (value - 32.0) * 5.0 / 9.0
    return value


def humidity_to_percent(value: float, unit: str | None) -> float:
    """Return relative humidity normalised to the ``0-100 %`` range.

    Args:
        value: Numeric humidity value as reported by the source.
        unit:  ``ATTR_UNIT_OF_MEASUREMENT`` string, or ``None``.

    Returns:
        Humidity in percent (``0.0-100.0``).

    Notes:
        When *unit* is ``"%"`` the value is returned unchanged.
        When *unit* is ``None`` **and** the value is within ``[0.0, 1.0]``
        it is assumed to be a normalised fraction (e.g. ESPHome custom
        sensors) and multiplied by 100.  Values outside ``[0.0, 1.0]``
        with no unit are returned as-is (assumed to already be percent).
    """
    if unit == "%":
        return value
    # Heuristic: unitless value in [0, 1] → treat as 0-1 fraction
    if unit is None and 0.0 <= value <= 1.0:
        return value * 100.0
    return value


# ---------------------------------------------------------------------------
# EASCDataProvider
# ---------------------------------------------------------------------------


class EASCDataProvider:
    """Single access point for temperature and humidity used by advanced sensors.

    Args:
        hass:        Home Assistant instance (used to read entity states).
        coordinator: The ``VmcHeltyCoordinator`` for the current device
                     (used to read VMC sensor data).
    """

    def __init__(self, hass: HomeAssistant, coordinator) -> None:
        self._hass = hass
        self._coordinator = coordinator

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_temperature(self, source: str) -> float | None:
        """Return internal temperature in °C from *source*.

        ``source`` is either :data:`~.const.EASC_SOURCE_VMC` (read from the
        VMC device, position 1 of the VMGI response) or an HA entity_id.

        When an external entity is configured but unavailable, the method
        falls back to the VMC internal temperature and logs a warning.

        Args:
            source: ``"vmc"`` or a HA entity_id string.

        Returns:
            Temperature in °C, or ``None`` if both the external source
            **and** the VMC fallback are unavailable.
        """
        if source == EASC_SOURCE_VMC:
            value = self._vmc_temperature_internal()
            _LOGGER.debug("EASC temp_int: source=vmc value=%s°C", value)
            return value

        value = self._entity_temperature(source)
        if value is None:
            _LOGGER.warning(
                "EASC: temp source '%s' unavailable, falling back to VMC internal",
                source,
            )
            fallback = self._vmc_temperature_internal()
            _LOGGER.debug(
                "EASC temp_int: fallback=vmc value=%s°C (entity '%s' unavailable)",
                fallback,
                source,
            )
            return fallback
        _LOGGER.debug("EASC temp_int: source=%s value=%s°C", source, value)
        return value

    def get_temperature_external(self, source: str) -> float | None:
        """Return external temperature in °C from *source*.

        Like :meth:`get_temperature` but falls back to the VMC *external*
        temperature (position 2 of the VMGI response) when the external
        entity is unavailable.

        Args:
            source: ``"vmc"`` or a HA entity_id string.

        Returns:
            Temperature in °C, or ``None`` if both the external source
            **and** the VMC fallback are unavailable.
        """
        if source == EASC_SOURCE_VMC:
            value = self._vmc_temperature_external()
            _LOGGER.debug("EASC temp_ext: source=vmc value=%s°C", value)
            return value

        value = self._entity_temperature(source)
        if value is None:
            _LOGGER.warning(
                "EASC: ext temp source '%s' unavailable, falling back to VMC",
                source,
            )
            fallback = self._vmc_temperature_external()
            _LOGGER.debug(
                "EASC temp_ext: fallback=vmc value=%s°C (entity '%s' unavailable)",
                fallback,
                source,
            )
            return fallback
        _LOGGER.debug("EASC temp_ext: source=%s value=%s°C", source, value)
        return value

    def get_humidity(self, source: str) -> float | None:
        """Return relative humidity in percent (``0-100``) from *source*.

        ``source`` is either :data:`~.const.EASC_SOURCE_VMC` (read from the
        VMC device, position 3 of the VMGI response) or an HA entity_id.

        When an external entity is configured but unavailable, the method
        falls back to the VMC humidity and logs a warning.

        Args:
            source: ``"vmc"`` or a HA entity_id string.

        Returns:
            Humidity in percent, or ``None`` if both the external source
            **and** the VMC fallback are unavailable.
        """
        if source == EASC_SOURCE_VMC:
            value = self._vmc_humidity()
            _LOGGER.debug("EASC humidity: source=vmc value=%s%%", value)
            return value

        value = self._entity_humidity(source)
        if value is None:
            _LOGGER.warning(
                "EASC: humidity source '%s' unavailable, falling back to VMC",
                source,
            )
            fallback = self._vmc_humidity()
            _LOGGER.debug(
                "EASC humidity: fallback=vmc value=%s%% (entity '%s' unavailable)",
                fallback,
                source,
            )
            return fallback
        _LOGGER.debug("EASC humidity: source=%s value=%s%%", source, value)
        return value

    def get_entity_state(self, entity_id: str) -> str | None:
        """Return the raw state string of a HA entity.

        Args:
            entity_id: A valid HA entity_id string.

        Returns:
            The state string, or ``None`` when the entity does not exist or
            its state is ``unavailable`` / ``unknown``.
        """
        state = self._hass.states.get(entity_id)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None
        return state.state

    # ------------------------------------------------------------------
    # VMC data helpers
    # ------------------------------------------------------------------

    def _parse_vmgi(self) -> list[str] | None:
        """Parse the VMGI response from coordinator data.

        Returns:
            List of comma-split parts, or ``None`` on any parse error.
        """
        if not self._coordinator.data:
            return None
        sensors_data = self._coordinator.data.get("sensors", "")
        if not sensors_data or not sensors_data.startswith("VMGI"):
            return None
        parts: list[str] = sensors_data.split(",")
        if len(parts) < MIN_RESPONSE_PARTS:
            return None
        return parts

    def _vmc_temperature_internal(self) -> float | None:
        """Return internal temperature from VMGI position 1 (tenths of °C)."""
        parts = self._parse_vmgi()
        if parts is None:
            return None
        try:
            return float(parts[1]) / 10.0
        except (ValueError, IndexError):
            return None

    def _vmc_temperature_external(self) -> float | None:
        """Return external temperature from VMGI position 2 (tenths of °C)."""
        parts = self._parse_vmgi()
        if parts is None:
            return None
        try:
            return float(parts[2]) / 10.0
        except (ValueError, IndexError):
            return None

    def _vmc_humidity(self) -> float | None:
        """Return relative humidity from VMGI position 3 (tenths of %)."""
        parts = self._parse_vmgi()
        if parts is None:
            return None
        try:
            return float(parts[3]) / 10.0
        except (ValueError, IndexError):
            return None

    # ------------------------------------------------------------------
    # External entity helpers
    # ------------------------------------------------------------------

    def _entity_temperature(self, entity_id: str) -> float | None:
        """Read temperature from a HA entity and return it in °C."""
        raw = self.get_entity_state(entity_id)
        if raw is None:
            return None
        try:
            value = float(raw)
        except (ValueError, TypeError):
            return None

        state_obj = self._hass.states.get(entity_id)
        unit = state_obj.attributes.get(ATTR_UNIT_OF_MEASUREMENT) if state_obj else None
        return celsius_from_unit(value, unit)

    def _entity_humidity(self, entity_id: str) -> float | None:
        """Read humidity from a HA entity and return it in percent (0-100)."""
        raw = self.get_entity_state(entity_id)
        if raw is None:
            return None
        try:
            value = float(raw)
        except (ValueError, TypeError):
            return None

        state_obj = self._hass.states.get(entity_id)
        unit = state_obj.attributes.get(ATTR_UNIT_OF_MEASUREMENT) if state_obj else None
        return humidity_to_percent(value, unit)
