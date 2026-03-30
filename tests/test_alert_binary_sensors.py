"""Tests for alert binary sensors."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

from homeassistant.util import dt as dt_util

from custom_components.vmc_helty_flow.const import FILTER_MAX_HOURS, FILTER_STATUS_POOR
from custom_components.vmc_helty_flow.sensor import (
    VmcHeltyAirQualityAlertBinarySensor,
    VmcHeltyCondensationRiskBinarySensor,
    VmcHeltyFilterWarningBinarySensor,
    VmcHeltyOfflineBinarySensor,
)


def _build_vmgi(
    temp_internal_tenths: int,
    temp_external_tenths: int,
    humidity_tenths: int,
    co2_ppm: int,
) -> str:
    """Build a valid VMGI payload with enough parts for parsing."""
    return (
        f"VMGI,{temp_internal_tenths},{temp_external_tenths},{humidity_tenths},"
        f"{co2_ppm},0,0,0,0,0,0,0,0,0,0"
    )


def test_air_quality_alert_triggers_after_five_minutes(monkeypatch) -> None:
    """Air quality alert turns on only after 5 minutes above threshold."""
    coordinator = MagicMock()
    coordinator.name_slug = "vmc_helty_testvmc"
    coordinator.name = "TestVMC"
    coordinator.data = {"sensors": _build_vmgi(240, 220, 600, 1200)}

    sensor_entity = VmcHeltyAirQualityAlertBinarySensor(coordinator)

    base_time = datetime(2026, 3, 26, 10, 0, tzinfo=dt_util.UTC)
    current_time = [base_time]
    monkeypatch.setattr(dt_util, "utcnow", lambda: current_time[0])

    assert sensor_entity.is_on is False

    current_time[0] = base_time + timedelta(minutes=4, seconds=59)
    assert sensor_entity.is_on is False

    current_time[0] = base_time + timedelta(minutes=5)
    assert sensor_entity.is_on is True

    coordinator.data = {"sensors": _build_vmgi(240, 220, 600, 900)}
    assert sensor_entity.is_on is False


def test_condensation_risk_alert_on_with_low_delta() -> None:
    """Condensation risk alert is on when dew point delta is below 2°C."""
    coordinator = MagicMock()
    coordinator.name_slug = "vmc_helty_testvmc"
    coordinator.name = "TestVMC"

    # Internal/external temperatures very close -> low dew point delta
    coordinator.data = {"sensors": _build_vmgi(240, 231, 600, 700)}

    sensor_entity = VmcHeltyCondensationRiskBinarySensor(coordinator)

    assert sensor_entity.is_on is True


def test_condensation_risk_alert_off_with_safe_delta() -> None:
    """Condensation risk alert is off when dew point delta is safely above 2°C."""
    coordinator = MagicMock()
    coordinator.name_slug = "vmc_helty_testvmc"
    coordinator.name = "TestVMC"

    # Temperatures far apart -> high dew point delta
    coordinator.data = {"sensors": _build_vmgi(240, 180, 600, 700)}

    sensor_entity = VmcHeltyCondensationRiskBinarySensor(coordinator)

    assert sensor_entity.is_on is False


def test_offline_alert_reflects_coordinator_status() -> None:
    """Offline alert follows coordinator.last_update_success state."""
    coordinator = MagicMock()
    coordinator.name_slug = "vmc_helty_testvmc"
    coordinator.name = "TestVMC"

    sensor_entity = VmcHeltyOfflineBinarySensor(coordinator)

    coordinator.last_update_success = True
    assert sensor_entity.is_on is False

    coordinator.last_update_success = False
    assert sensor_entity.is_on is True


def test_filter_warning_off_when_filter_is_new() -> None:
    """Filter warning is off when filter life is above the warning threshold."""
    coordinator = MagicMock()
    coordinator.name_slug = "vmc_helty_testvmc"
    coordinator.name = "TestVMC"
    coordinator.data = {"filter_hours": FILTER_MAX_HOURS}

    sensor_entity = VmcHeltyFilterWarningBinarySensor(coordinator)

    assert sensor_entity.is_on is False


def test_filter_warning_off_when_above_threshold() -> None:
    """Filter warning is off when life percentage is above FILTER_STATUS_POOR."""
    coordinator = MagicMock()
    coordinator.name_slug = "vmc_helty_testvmc"
    coordinator.name = "TestVMC"
    # 20% remaining - above the 10% threshold
    hours_at_20_percent = int(FILTER_MAX_HOURS * 0.20)
    coordinator.data = {"filter_hours": hours_at_20_percent}

    sensor_entity = VmcHeltyFilterWarningBinarySensor(coordinator)

    assert sensor_entity.is_on is False


def test_filter_warning_on_at_threshold() -> None:
    """Filter warning turns on exactly at FILTER_STATUS_POOR (10%) threshold."""
    coordinator = MagicMock()
    coordinator.name_slug = "vmc_helty_testvmc"
    coordinator.name = "TestVMC"
    # Exactly 10% remaining - at the threshold
    hours_at_threshold = int(FILTER_MAX_HOURS * FILTER_STATUS_POOR / 100)
    coordinator.data = {"filter_hours": hours_at_threshold}

    sensor_entity = VmcHeltyFilterWarningBinarySensor(coordinator)

    assert sensor_entity.is_on is True


def test_filter_warning_on_below_threshold() -> None:
    """Filter warning is on when filter life is below the warning threshold."""
    coordinator = MagicMock()
    coordinator.name_slug = "vmc_helty_testvmc"
    coordinator.name = "TestVMC"
    # 5% remaining - well below the 10% threshold
    hours_at_5_percent = int(FILTER_MAX_HOURS * 0.05)
    coordinator.data = {"filter_hours": hours_at_5_percent}

    sensor_entity = VmcHeltyFilterWarningBinarySensor(coordinator)

    assert sensor_entity.is_on is True


def test_filter_warning_on_when_exhausted() -> None:
    """Filter warning is on when filter is fully exhausted (0 hours remaining)."""
    coordinator = MagicMock()
    coordinator.name_slug = "vmc_helty_testvmc"
    coordinator.name = "TestVMC"
    coordinator.data = {"filter_hours": 0}

    sensor_entity = VmcHeltyFilterWarningBinarySensor(coordinator)

    assert sensor_entity.is_on is True


def test_filter_warning_off_when_no_data() -> None:
    """Filter warning is off when coordinator data is unavailable."""
    coordinator = MagicMock()
    coordinator.name_slug = "vmc_helty_testvmc"
    coordinator.name = "TestVMC"
    coordinator.data = None

    sensor_entity = VmcHeltyFilterWarningBinarySensor(coordinator)

    assert sensor_entity.is_on is False


def test_filter_warning_extra_state_attributes() -> None:
    """Filter warning extra_state_attributes returns expected keys."""
    coordinator = MagicMock()
    coordinator.name_slug = "vmc_helty_testvmc"
    coordinator.name = "TestVMC"
    hours = int(FILTER_MAX_HOURS * 0.05)
    coordinator.data = {"filter_hours": hours}

    sensor_entity = VmcHeltyFilterWarningBinarySensor(coordinator)
    attrs = sensor_entity.extra_state_attributes

    assert attrs is not None
    assert attrs["filter_hours_remaining"] == hours
    assert attrs["filter_life_percentage"] == round(hours / FILTER_MAX_HOURS * 100, 1)
    assert attrs["filter_max_hours"] == FILTER_MAX_HOURS


def test_filter_warning_attributes_none_when_no_filter_data() -> None:
    """Filter warning extra_state_attributes returns None when filter_hours missing."""
    coordinator = MagicMock()
    coordinator.name_slug = "vmc_helty_testvmc"
    coordinator.name = "TestVMC"
    coordinator.data = {"status": "VMGO,1,1,240,600"}

    sensor_entity = VmcHeltyFilterWarningBinarySensor(coordinator)

    assert sensor_entity.extra_state_attributes is None
