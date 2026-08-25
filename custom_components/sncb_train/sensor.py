"""Sensor platform for SNCB Train Tracker."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SncbTrainCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    coordinator: SncbTrainCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = [
        SncbDelayFromSensor(coordinator, entry),
        SncbDelayToSensor(coordinator, entry),
        SncbStatusSensor(coordinator, entry),
        SncbCurrentStationSensor(coordinator, entry),
        SncbCurrentDelaySensor(coordinator, entry),
        SncbNextStationSensor(coordinator, entry),
        SncbNextDelaySensor(coordinator, entry),
        SncbPlatformFromSensor(coordinator, entry),
    ]

    async_add_entities(sensors)


class SncbBaseSensor(CoordinatorEntity[SncbTrainCoordinator], SensorEntity):
    """Base class for SNCB train sensors."""

    def __init__(self, coordinator: SncbTrainCoordinator, entry: ConfigEntry) -> None:
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
        return self.coordinator.last_update_success and self.coordinator.data is not None


class SncbDelayFromSensor(SncbBaseSensor):
    """Arrival delay at the departure station."""

    _attr_native_unit_of_measurement = "min"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:clock-alert-outline"

    def __init__(self, coordinator: SncbTrainCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_delay_from"
        self._attr_name = f"Retard arrivée {coordinator.station_from.title()}"

    @property
    def native_value(self) -> int | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("delay_from_minutes")

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data or {}
        return {
            "scheduled": data.get("scheduled_from"),
            "platform": data.get("platform_from"),
            "status": data.get("status"),
            "current_station": data.get("current_station"),
            "vehicle": data.get("vehicle"),
            "last_update": data.get("last_update"),
        }


class SncbDelayToSensor(SncbBaseSensor):
    """Arrival delay at the destination station."""

    _attr_native_unit_of_measurement = "min"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:clock-alert"

    def __init__(self, coordinator: SncbTrainCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_delay_to"
        self._attr_name = f"Retard arrivée {coordinator.station_to.title()}"

    @property
    def native_value(self) -> int | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("delay_to_minutes")

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data or {}
        return {
            "scheduled": data.get("scheduled_to"),
            "platform": data.get("platform_to"),
            "status": data.get("status"),
            "current_station": data.get("current_station"),
            "vehicle": data.get("vehicle"),
            "last_update": data.get("last_update"),
        }


class SncbStatusSensor(SncbBaseSensor):
    """Overall status of the train."""

    _attr_name = "Statut"
    _attr_icon = "mdi:train"

    def __init__(self, coordinator: SncbTrainCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_status"

    @property
    def native_value(self) -> str | None:
        if not self.coordinator.data:
            return None
        status = self.coordinator.data.get("status")
        mapping = {
            "not_departed": "Pas encore parti",
            "at_departure": "À quai (départ)",
            "en_route": "En route",
            "at_destination": "À quai (arrivée)",
            "passed": "Déjà passé",
            "canceled": "Annulé",
            "not_found": "Non circulant aujourd'hui",
            "no_stops": "Données indisponibles",
            "station_not_found": "Gare non trouvée",
            "temporary_error": "Erreur temporaire API",
            "data_lost": "Données perdues (API)",
        }
        return mapping.get(status, status)

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data or {}
        return {
            "delay_from": data.get("delay_from_minutes"),
            "delay_to": data.get("delay_to_minutes"),
            "current_station": data.get("current_station"),
            "next_station": data.get("next_station"),
            "scheduled_from": data.get("scheduled_from"),
            "scheduled_to": data.get("scheduled_to"),
            "api_warning": data.get("api_warning"),
            "vehicle": data.get("vehicle"),
        }


class SncbCurrentStationSensor(SncbBaseSensor):
    """Last station the train has left / current position."""

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


class SncbCurrentDelaySensor(SncbBaseSensor):
    """Arrival delay at the current station."""

    _attr_name = "Retard position actuelle"
    _attr_native_unit_of_measurement = "min"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator: SncbTrainCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_current_delay"

    @property
    def native_value(self) -> int | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("current_delay_minutes")

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data or {}
        return {
            "station": data.get("current_station"),
        }


class SncbNextStationSensor(SncbBaseSensor):
    """Next station on the route."""

    _attr_name = "Prochaine gare"
    _attr_icon = "mdi:map-marker-path"

    def __init__(self, coordinator: SncbTrainCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_next_station"

    @property
    def native_value(self) -> str | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("next_station")


class SncbNextDelaySensor(SncbBaseSensor):
    """Arrival delay at the next station."""

    _attr_name = "Retard prochaine gare"
    _attr_native_unit_of_measurement = "min"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:clock-fast"

    def __init__(self, coordinator: SncbTrainCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_next_delay"

    @property
    def native_value(self) -> int | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("next_delay_minutes")

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data or {}
        return {
            "station": data.get("next_station"),
        }


class SncbPlatformFromSensor(SncbBaseSensor):
    """Platform at the departure station."""

    _attr_icon = "mdi:railroad-light"

    def __init__(self, coordinator: SncbTrainCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_platform_from"
        self._attr_name = f"Quai {coordinator.station_from.title()}"

    @property
    def native_value(self) -> str | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("platform_from")
