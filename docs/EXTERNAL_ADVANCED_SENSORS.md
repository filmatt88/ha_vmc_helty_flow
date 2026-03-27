# External Advanced Sensor Configuration (EASC)

EASC lets the four calculated sensors — **Absolute Humidity**, **Dew Point**, **Comfort Index**, and **Dew Point Delta** — read temperature and humidity from any Home Assistant entity instead of (or as a fallback for) the VMC device's built-in sensors.

---

## Table of Contents

1. [Why use EASC?](#why-use-easc)
2. [Supported sensors](#supported-sensors)
3. [Configuration step-by-step](#configuration-step-by-step)
4. [Source field reference](#source-field-reference)
5. [Formula selection](#formula-selection)
6. [Integration examples](#integration-examples)
   - [Netatmo weather station](#netatmo-weather-station)
   - [ESPHome custom sensor](#esphome-custom-sensor)
   - [Home Assistant weather entity](#home-assistant-weather-entity)
7. [Automatic fallback](#automatic-fallback)
8. [Troubleshooting](#troubleshooting)

---

## Why use EASC?

The VMC Helty Flow device measures temperature and humidity at its installation point (typically inside the ventilation duct or at the wall panel). EASC allows you to replace those readings with more representative values — for example from a room thermostat, a weather station, or an outdoor sensor — while preserving the automatic fallback to the VMC data if the external source becomes unavailable.

---

## Supported sensors

| Sensor | Configurable sources |
|--------|---------------------|
| **Absolute Humidity** | Temperature + Humidity |
| **Dew Point** | Temperature + Humidity |
| **Comfort Index** | Temperature + Humidity |
| **Dew Point Delta** | Internal temperature + External temperature + Humidity |

---

## Configuration step-by-step

1. Go to **Settings → Devices & Services → VMC Helty Flow → Configure**.
2. Enable **"Configure advanced sensors (EASC)"** and press **Submit**.
3. The **Advanced Sensors** form appears with one section per sensor:
   - Toggle **Enable** to activate the sensor.
   - In the **source** fields enter either:
     - `vmc` — read from the VMC device (default).
     - A valid Home Assistant **entity_id** (e.g. `sensor.living_room_temperature`).
   - Select the **formula** (`magnus` or `custom`) — see [Formula selection](#formula-selection).
4. Press **Submit**. The integration restarts with the new configuration.

> **Note:** The sensors always compute a value. The *Enable* checkbox is informational — it signals your intent and appears in diagnostics, but does not prevent computation when the source fields are left at `vmc`.

---

## Source field reference

| Field | Sensor | Accepted values |
|-------|--------|----------------|
| `abs_hum_temperature_source` | Absolute Humidity | `vmc` or entity_id |
| `abs_hum_humidity_source` | Absolute Humidity | `vmc` or entity_id |
| `dew_point_temperature_source` | Dew Point | `vmc` or entity_id |
| `dew_point_humidity_source` | Dew Point | `vmc` or entity_id |
| `comfort_index_temperature_source` | Comfort Index | `vmc` or entity_id |
| `comfort_index_humidity_source` | Comfort Index | `vmc` or entity_id |
| `dew_point_delta_temperature_internal` | Dew Point Delta | `vmc` or entity_id |
| `dew_point_delta_temperature_external` | Dew Point Delta | `vmc` or entity_id |
| `dew_point_delta_humidity_source` | Dew Point Delta | `vmc` or entity_id |

### Valid entity_id formats

- `sensor.living_room_temperature`
- `sensor.outdoor_humidity`
- `weather.home` *(state must be a numeric temperature in °C or °F)*

The integration reads the entity's **state** as a float and applies automatic unit conversion:
- **Temperature**: `°F` or `F` → converted to `°C`; all other units assumed to be `°C`.
- **Humidity**: `%` → used as-is; no unit and value in `[0.0, 1.0]` → multiplied by 100.

---

## Formula selection

Two formulas are available for dew point / saturation vapour pressure calculations:

| Key | Name | Coefficients | Recommended use |
|-----|------|-------------|----------------|
| `magnus` | Magnus-Tetens | a=17.27, b=237.7 | General purpose, −40 °C to +50 °C |
| `custom` | August-Roche-Magnus | a=17.625, b=243.04 | WMO standard, more accurate 0–60 °C |

The difference between the two formulas is typically less than 0.1 °C in normal indoor conditions. Use `custom` if you require WMO-compliant calculations.

---

## Integration examples

### Netatmo weather station

Netatmo entities typically expose temperature in `°C` and humidity in `%`.

```yaml
# In the EASC options form:
abs_hum_temperature_source: sensor.netatmo_living_room_temperature
abs_hum_humidity_source:    sensor.netatmo_living_room_humidity
dew_point_temperature_source: sensor.netatmo_living_room_temperature
dew_point_humidity_source:    sensor.netatmo_living_room_humidity
# For Dew Point Delta — use outdoor module for external temperature:
dew_point_delta_temperature_internal: sensor.netatmo_living_room_temperature
dew_point_delta_temperature_external: sensor.netatmo_outdoor_temperature
dew_point_delta_humidity_source:      sensor.netatmo_living_room_humidity
```

### ESPHome custom sensor

ESPHome sensors typically report temperature in `°C` and humidity in `%`. If your sensor reports humidity as a normalised fraction (0.0–1.0) without a unit, the integration will automatically multiply by 100.

```yaml
abs_hum_temperature_source: sensor.esphome_room_temperature
abs_hum_humidity_source:    sensor.esphome_room_humidity
```

If the ESPHome sensor reports temperature in Fahrenheit, add `unit_of_measurement: "°F"` in your ESPHome YAML — the integration will convert it automatically.

### Home Assistant weather entity

Weather entities expose temperature via their state. Note that `weather.home` state is the temperature in the unit configured in HA (Settings → System → General → Unit system).

```yaml
# When using weather entity for outdoor temperature in Dew Point Delta:
dew_point_delta_temperature_external: weather.home
# The state (e.g. "8.5") is read directly; ensure HA unit system is °C
# or that the entity reports °F (will be auto-converted).
```

> **Tip:** If your weather entity state is not numeric (e.g. `"sunny"`), the integration will fall back to the VMC external temperature and log a warning.

---

## Automatic fallback

When an external entity is configured but:
- the entity does not exist,
- its state is `unavailable` or `unknown`, or
- its state cannot be parsed as a number,

the integration **automatically falls back** to the corresponding VMC sensor value and logs a `WARNING` in the Home Assistant logs:

```
WARNING  custom_components.vmc_helty_flow.easc_provider:
  EASC: temperature source 'sensor.missing' unavailable, falling back to VMC internal
```

This means the advanced sensors continue to produce values even when external sources are temporarily offline.

---

## Troubleshooting

### Sensor shows unexpected values

1. Check **Developer Tools → States** to verify the entity_id exists and its state is a valid number.
2. Check the **Diagnostics** page (Settings → Devices & Services → VMC Helty Flow → Download diagnostics). The `easc.sensors` section shows:
   - `enabled`: whether the sensor is marked active.
   - `*_source.available`: whether the configured entity is reachable.
   - `*_source.state`: the last known state value.
   - `*_source.last_updated`: when the entity was last updated.

### Fallback is happening unexpectedly

Enable debug logging for the integration:

```yaml
# configuration.yaml
logger:
  default: warning
  logs:
    custom_components.vmc_helty_flow.easc_provider: debug
```

Then check the logs for `EASC temp_int:`, `EASC temp_ext:`, and `EASC humidity:` lines showing which source was used and the value read.

### Source validation error in the options form

The source field must be either exactly `vmc` or a valid HA entity_id in the format `domain.object_id` (e.g. `sensor.my_sensor`). Spaces and uppercase letters are not accepted.

### Formula field validation error

The formula field accepts only `magnus` or `custom`. Any other value will be rejected with an error.
