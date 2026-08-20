"""Sensor platform for SNCB Train Tracker."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_CANCELED,
    ATTR_CURRENT_STATION,
    ATTR_DELAY_MINUTES,
    ATTR_LAST_UPDATE,
    ATTR_LEFT_GEMBLOUX,
    ATTR_OCCUPANCY,
    ATTR_PLATFORM,
    ATTR_SCHEDULED_TIME,
    ATTR_SHORTNAME,
    ATTR_STATUS,
    ATTR_VEHICLE,
    DOMAIN,
)
from .coordinator import SncbTrainCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    coordinator: SncbTrainCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = [
        SncbDelaySensor(coordinator, entry),
        SncbStatusSensor(coordinator, entry),
        SncbCurrentStationSensor(coordinator, entry),
        SncbPlatformSensor(coordinator, entry),
    ]

    async_add_entities(sensors)


class SncbBaseSensor(CoordinatorEntity[SncbTrainCoordinator], SensorEntity):
    """Base class for SNCB train sensors."""

    def __init__(self, coordinator: SncbTrainCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_has_entity_name = True
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": coordinator.friendly_name,
            "manufacturer": "SNCB / iRail",
            "model": coordinator.api_vehicle_id,
        }

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data is not None


class SncbDelaySensor(SncbBaseSensor):
    """Sensor for delay at the monitored station (minutes)."""

    _attr_name = "Retard"
    _attr_native_unit_of_measurement = "min"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:clock-alert"

    def __init__(self, coordinator: SncbTrainCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_delay"

    @property
    def native_value(self) -> int | None:
        """Return the delay in minutes."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("delay_minutes")

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra attributes."""
        data = self.coordinator.data or {}
        return {
            ATTR_STATUS: data.get("status"),
            ATTR_PLATFORM: data.get("platform"),
            ATTR_SCHEDULED_TIME: data.get("scheduled_time"),
            ATTR_CURRENT_STATION: data.get("current_station"),
            ATTR_OCCUPANCY: data.get("occupancy"),
            ATTR_CANCELED: data.get("canceled"),
            ATTR_LEFT_GEMBLOUX: data.get("left_station"),
            ATTR_VEHICLE: data.get("vehicle"),
            ATTR_SHORTNAME: data.get("shortname"),
            ATTR_LAST_UPDATE: data.get("last_update"),
        }


class SncbStatusSensor(SncbBaseSensor):
    """Sensor for overall status of the train regarding the monitored station."""

    _attr_name = "Statut"
    _attr_icon = "mdi:train"

    def __init__(self, coordinator: SncbTrainCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_status"

    @property
    def native_value(self) -> str | None:
        """Return the status."""
        if not self.coordinator.data:
            return None
        status = self.coordinator.data.get("status")
        # Translate to French for nicer display
        mapping = {
            "not_departed": "Pas encore parti",
            "en_route": "En route",
            "at_station": "À quai",
            "passed": "Déjà passé",
            "canceled": "Annulé",
            "not_found": "Non circulant aujourd'hui",
            "no_stops": "Données indisponibles",
            "station_not_found": "Gare non trouvée",
        }
        return mapping.get(status, status)

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data or {}
        return {
            ATTR_DELAY_MINUTES: data.get("delay_minutes"),
            ATTR_CURRENT_STATION: data.get("current_station"),
            ATTR_PLATFORM: data.get("platform"),
            ATTR_SCHEDULED_TIME: data.get("scheduled_time"),
            ATTR_VEHICLE: data.get("vehicle"),
        }


class SncbCurrentStationSensor(SncbBaseSensor):
    """Sensor showing the last station the train has left."""

    _attr_name = "Position actuelle"
    _attr_icon = "mdi:map-marker"

    def __init__(self, coordinator: SncbTrainCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_current_station"

    @property
    def native_value(self) -> str | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("current_station")


class SncbPlatformSensor(SncbBaseSensor):
    """Sensor for the platform at the monitored station."""

    _attr_name = "Quai"
    _attr_icon = "mdi:railroad-light"

    def __init__(self, coordinator: SncbTrainCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_platform"

    @property
    def native_value(self) -> str | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("platform")
