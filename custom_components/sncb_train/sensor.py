"""Sensor platform for SNCB Train Tracker."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
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
    """Set up sensors from a config entry."""
    coordinator: SncbTrainCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = [
        SncbStatusSensor(coordinator, entry),
        SncbCurrentStationSensor(coordinator, entry),
        SncbCurrentDelaySensor(coordinator, entry),
        SncbNextStationSensor(coordinator, entry),
        SncbNextDelaySensor(coordinator, entry),
        SncbDelayFromSensor(coordinator, entry),
        SncbDelayToSensor(coordinator, entry),
        SncbPlatformFromSensor(coordinator, entry),
    ]

    async_add_entities(sensors, update_before_add=True)


class SncbBaseSensor(CoordinatorEntity[SncbTrainCoordinator], SensorEntity):
    """Base class for SNCB train sensors."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SncbTrainCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=coordinator.friendly_name,
            manufacturer="SNCB / iRail",
            model=coordinator.api_vehicle_id,
        )

    @property
    def available(self) -> bool:
        """Always available once coordinator has returned any payload."""
        return self.coordinator.data is not None


class SncbStatusSensor(SncbBaseSensor):
    """Overall status of the train."""

    _attr_name = "Statut"
    _attr_icon = "mdi:train"

    def __init__(self, coordinator: SncbTrainCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_status"

    @property
    def native_value(self) -> str:
        data = self.coordinator.data or {}
        status = data.get("status") or "unknown"
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
            "unknown": "Inconnu",
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
            "last_update": data.get("last_update"),
        }


class SncbCurrentStationSensor(SncbBaseSensor):
    """Current / last station."""

    _attr_name = "Position actuelle"
    _attr_icon = "mdi:map-marker"

    def __init__(self, coordinator: SncbTrainCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_current_station"

    @property
    def native_value(self) -> str | None:
        data = self.coordinator.data or {}
        return data.get("current_station")


class SncbCurrentDelaySensor(SncbBaseSensor):
    """Delay at current station."""

    _attr_name = "Retard position actuelle"
    _attr_native_unit_of_measurement = "min"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator: SncbTrainCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_current_delay"

    @property
    def native_value(self) -> int | None:
        data = self.coordinator.data or {}
        return data.get("current_delay_minutes")

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data or {}
        return {"station": data.get("current_station")}


class SncbNextStationSensor(SncbBaseSensor):
    """Next station."""

    _attr_name = "Prochaine gare"
    _attr_icon = "mdi:map-marker-path"

    def __init__(self, coordinator: SncbTrainCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_next_station"

    @property
    def native_value(self) -> str | None:
        data = self.coordinator.data or {}
        return data.get("next_station")


class SncbNextDelaySensor(SncbBaseSensor):
    """Delay at next station."""

    _attr_name = "Retard prochaine gare"
    _attr_native_unit_of_measurement = "min"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:clock-fast"

    def __init__(self, coordinator: SncbTrainCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_next_delay"

    @property
    def native_value(self) -> int | None:
        data = self.coordinator.data or {}
        return data.get("next_delay_minutes")

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data or {}
        return {"station": data.get("next_station")}


class SncbDelayFromSensor(SncbBaseSensor):
    """Arrival delay at departure station."""

    _attr_native_unit_of_measurement = "min"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:clock-alert-outline"

    def __init__(self, coordinator: SncbTrainCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_delay_from"
        self._attr_name = f"Retard arrivée {coordinator.station_from.title()}"

    @property
    def native_value(self) -> int | None:
        data = self.coordinator.data or {}
        return data.get("delay_from_minutes")

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data or {}
        return {
            "scheduled": data.get("scheduled_from"),
            "platform": data.get("platform_from"),
            "last_update": data.get("last_update"),
        }


class SncbDelayToSensor(SncbBaseSensor):
    """Arrival delay at destination station."""

    _attr_native_unit_of_measurement = "min"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:clock-alert"

    def __init__(self, coordinator: SncbTrainCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_delay_to"
        self._attr_name = f"Retard arrivée {coordinator.station_to.title()}"

    @property
    def native_value(self) -> int | None:
        data = self.coordinator.data or {}
        return data.get("delay_to_minutes")

    @property
    def extra_state_attributes(self) -> dict:
        data = self.coordinator.data or {}
        return {
            "scheduled": data.get("scheduled_to"),
            "platform": data.get("platform_to"),
            "last_update": data.get("last_update"),
        }


class SncbPlatformFromSensor(SncbBaseSensor):
    """Platform at departure station."""

    _attr_icon = "mdi:railroad-light"

    def __init__(self, coordinator: SncbTrainCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_platform_from"
        self._attr_name = f"Quai {coordinator.station_from.title()}"

    @property
    def native_value(self) -> str | None:
        data = self.coordinator.data or {}
        return data.get("platform_from")
