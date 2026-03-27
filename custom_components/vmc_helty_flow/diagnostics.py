"""Diagnostics support for VMC Helty Flow integration."""

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_EASC_ABSOLUTE_HUMIDITY,
    CONF_EASC_COMFORT_INDEX,
    CONF_EASC_CONFIG,
    CONF_EASC_DEW_POINT,
    CONF_EASC_DEW_POINT_DELTA,
    CONF_EASC_ENABLED,
    CONF_EASC_HUMIDITY_SOURCE,
    CONF_EASC_TEMPERATURE_EXTERNAL,
    CONF_EASC_TEMPERATURE_INTERNAL,
    CONF_EASC_TEMPERATURE_SOURCE,
    DIAG_LIGHTS_LEVEL_INDEX,
    DIAG_LIGHTS_TIMER_INDEX,
    DIAG_PANEL_LED_INDEX,
    DIAG_SENSORS_INDEX,
    DOMAIN,
    EASC_SOURCE_VMC,
)
from .easc_schema import get_sensor_config, validate_easc_config

# Campi sensibili da oscurare nei diagnostics
TO_REDACT = {
    "password",
    "network_password",
    "wifi_password",
    "ssid",
    "network_ssid",
    "wifi_ssid",
    "host",
    "ip",
    "mac",
    "serial_number",
    "unique_id",
    "username",
    "credentials",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    # Raccoglie i dati diagnostici
    diagnostics_data = {
        "config_entry": {
            "title": config_entry.title,
            "domain": config_entry.domain,
            "version": config_entry.version,
            "data": async_redact_data(config_entry.data, TO_REDACT),
            "options": async_redact_data(config_entry.options, TO_REDACT),
            "source": config_entry.source,
            # Il unique_id è considerato sensibile quindi oscurato
            "unique_id": config_entry.unique_id and "**REDACTED**",
        },
        "coordinator": {
            "ip": async_redact_data({"ip": coordinator.ip}, TO_REDACT)["ip"],
            "name": coordinator.name,
            "last_update_success": coordinator.last_update_success,
            "last_update": coordinator.last_update,
            "update_interval": coordinator.update_interval.total_seconds(),
            "data": async_redact_data(coordinator.data or {}, TO_REDACT),
        },
        "device_info": {
            "available": coordinator.last_update_success,
            "model": config_entry.data.get("model", "Unknown"),
            "manufacturer": config_entry.data.get("manufacturer", "Helty"),
        },
    }

    # Aggiunge statistiche aggiuntive se disponibili
    if coordinator.data:
        try:
            status = coordinator.data.get("status", "")
            if status and status.startswith("VMGO"):
                parts = status.split(",")
                diagnostics_data["device_status"] = {
                    "fan_speed_raw": parts[1] if len(parts) > 1 else "unknown",
                    "panel_led_raw": (
                        parts[DIAG_PANEL_LED_INDEX]
                        if len(parts) > DIAG_PANEL_LED_INDEX
                        else "unknown"
                    ),
                    "sensors_raw": (
                        parts[DIAG_SENSORS_INDEX]
                        if len(parts) > DIAG_SENSORS_INDEX
                        else "unknown"
                    ),
                    "lights_level_raw": (
                        parts[DIAG_LIGHTS_LEVEL_INDEX]
                        if len(parts) > DIAG_LIGHTS_LEVEL_INDEX
                        else "unknown"
                    ),
                    "lights_timer_raw": (
                        parts[DIAG_LIGHTS_TIMER_INDEX]
                        if len(parts) > DIAG_LIGHTS_TIMER_INDEX
                        else "unknown"
                    ),
                    "response_parts_count": len(parts),
                    # Non includere la risposta completa nei diagnostici,
                    # solo i valori rilevanti
                    "full_response": "**REDACTED**",
                }
        except Exception:
            diagnostics_data["device_status"] = {"parsing_error": True}

    # EASC configuration and entity availability
    easc_raw = config_entry.options.get(CONF_EASC_CONFIG, {})
    easc_cfg = validate_easc_config(easc_raw)

    def _entity_state(entity_id: str) -> dict:
        """Return availability info for a single source entity."""
        if entity_id == EASC_SOURCE_VMC:
            return {"source": "vmc", "available": True}
        state = hass.states.get(entity_id)
        if state is None:
            return {
                "source": entity_id,
                "available": False,
                "reason": "entity_not_found",
            }
        if state.state in ("unavailable", "unknown"):
            return {
                "source": entity_id,
                "available": False,
                "reason": state.state,
                "last_updated": (
                    state.last_updated.isoformat() if state.last_updated else None
                ),
            }
        return {
            "source": entity_id,
            "available": True,
            "state": state.state,
            "last_updated": (
                state.last_updated.isoformat() if state.last_updated else None
            ),
        }

    base_sensors = {
        CONF_EASC_ABSOLUTE_HUMIDITY: "absolute_humidity",
        CONF_EASC_DEW_POINT: "dew_point",
        CONF_EASC_COMFORT_INDEX: "comfort_index",
    }

    easc_diag: dict = {}
    for sensor_key, label in base_sensors.items():
        cfg = get_sensor_config(easc_cfg, sensor_key)
        easc_diag[label] = {
            "enabled": cfg.get(CONF_EASC_ENABLED, False),
            "temperature_source": _entity_state(
                cfg.get(CONF_EASC_TEMPERATURE_SOURCE, EASC_SOURCE_VMC)
            ),
            "humidity_source": _entity_state(
                cfg.get(CONF_EASC_HUMIDITY_SOURCE, EASC_SOURCE_VMC)
            ),
        }

    dpd_cfg = get_sensor_config(easc_cfg, CONF_EASC_DEW_POINT_DELTA)
    easc_diag["dew_point_delta"] = {
        "enabled": dpd_cfg.get(CONF_EASC_ENABLED, False),
        "temperature_internal_source": _entity_state(
            dpd_cfg.get(CONF_EASC_TEMPERATURE_INTERNAL, EASC_SOURCE_VMC)
        ),
        "temperature_external_source": _entity_state(
            dpd_cfg.get(CONF_EASC_TEMPERATURE_EXTERNAL, EASC_SOURCE_VMC)
        ),
        "humidity_source": _entity_state(
            dpd_cfg.get(CONF_EASC_HUMIDITY_SOURCE, EASC_SOURCE_VMC)
        ),
    }

    diagnostics_data["easc"] = {
        "configured": bool(easc_raw),
        "sensors": easc_diag,
    }

    return diagnostics_data


async def async_get_device_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry, _device
) -> dict:
    """Return diagnostics for a device entry."""
    return await async_get_config_entry_diagnostics(hass, config_entry)
