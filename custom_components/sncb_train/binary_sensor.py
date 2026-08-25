"""Binary sensors for SNCB Train Tracker."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SncbTrainCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors."""
    coordinator: SncbTrainCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ArrivedFromBinarySensor(coordinator, entry)], True)


class ArrivedFromBinarySensor(
    CoordinatorEntity[SncbTrainCoordinator], BinarySensorEntity
):
    """True when the train has arrived at the monitored departure station."""

    _attr_has_entity_name = True
    # No device_class → generic on/off (not "Home"/"Away")
    _attr_icon = "mdi:train-car"

    def __init__(self, coordinator: SncbTrainCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_arrived_from"
        self._attr_name = f"À quai {coordinator.station_from.title()}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=coordinator.friendly_name,
            manufacturer="SNCB / iRail",
            model=coordinator.api_vehicle_id,
        )

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        data = self.coordinator.data or {}
        return bool(data.get("arrived_from"))

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data or {}
        return {
            "station": self.coordinator.station_from.title(),
            "left": data.get("left_from"),
            "platform": data.get("platform_from"),
            "last_update": data.get("last_update"),
        }
