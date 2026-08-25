"""SNCB Train Tracker integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_NAME,
    CONF_STATION_FROM,
    CONF_STATION_TO,
    CONF_VEHICLE_ID,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_STATION_FROM,
    DEFAULT_STATION_TO,
    DOMAIN,
)
from .coordinator import SncbTrainCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SNCB Train Tracker from a config entry."""
    vehicle_id = entry.data[CONF_VEHICLE_ID]
    station_from = entry.data.get(CONF_STATION_FROM, DEFAULT_STATION_FROM)
    station_to = entry.data.get(CONF_STATION_TO, DEFAULT_STATION_TO)
    name = entry.data.get(CONF_NAME, vehicle_id)

    coordinator = SncbTrainCoordinator(
        hass=hass,
        vehicle_id=vehicle_id,
        station_from=station_from,
        station_to=station_to,
        name=name,
        scan_interval=entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL),
    )

    # Always register coordinator first so sensors can attach
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # First refresh: do not abort setup if API fails (coordinator returns empty data)
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
