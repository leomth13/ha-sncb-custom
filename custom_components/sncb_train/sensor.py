"""Sensors for SNCB Train Tracker."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SncbTrainCoordinator

STATUS_FR = {
    "not_departed": "Pas encore parti",
    "en_route": "En route",
    "passed": "Déjà passé",
    "canceled": "Annulé",
    "not_found": "Non circulant aujourd'hui",
    "no_stops": "Données indisponibles",
    "station_not_found": "Gare non trouvée",
    "temporary_error": "Erreur temporaire API",
    "data_lost": "Données perdues (API)",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator: SncbTrainCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            StatusSensor(coordinator, entry),
            CurrentStationSensor(coordinator, entry),
            CurrentDelaySensor(coordinator, entry),
            NextStationSensor(coordinator, entry),
            NextDelaySensor(coordinator, entry),
            DelayFromSensor(coordinator, entry),
            DelayToSensor(coordinator, entry),
            PlatformFromSensor(coordinator, entry),
            PlatformToSensor(coordinator, entry),
        ],
        True,
    )


class BaseSncbSensor(CoordinatorEntity[SncbTrainCoordinator], SensorEntity):
    """Shared base."""

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
        # Always available so UI never shows "indisponible"
        return True

    @property
    def _data(self) -> dict:
        return self.coordinator.data or {}


class StatusSensor(BaseSncbSensor):
    """Train status."""

    _attr_name = "Statut"
    _attr_icon = "mdi:train"

    def __init__(self, coordinator: SncbTrainCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_status"

    @property
    def native_value(self) -> str:
        status = self._data.get("status") or "unknown"
        return STATUS_FR.get(status, status)

    @property
    def extra_state_attributes(self) -> dict:
        d = self._data
        return {
            "vehicle": d.get("vehicle"),
            "current_station": d.get("current_station"),
            "next_station": d.get("next_station"),
            "delay_from": d.get("delay_from_minutes"),
            "delay_to": d.get("delay_to_minutes"),
            "scheduled_from": d.get("scheduled_from"),
            "scheduled_to": d.get("scheduled_to"),
            "api_warning": d.get("api_warning"),
            "last_update": d.get("last_update"),
        }


class CurrentStationSensor(BaseSncbSensor):
    """Current position."""

    _attr_name = "Position actuelle"
    _attr_icon = "mdi:map-marker"

    def __init__(self, coordinator: SncbTrainCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_current_station"

    @property
    def native_value(self) -> str | None:
        return self._data.get("current_station")


class CurrentDelaySensor(BaseSncbSensor):
    """Delay at current station."""

    _attr_name = "Retard position actuelle"
    _attr_icon = "mdi:clock-outline"
    _attr_native_unit_of_measurement = "min"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: SncbTrainCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_current_delay"

    @property
    def native_value(self) -> int | None:
        return self._data.get("current_delay_minutes")


class NextStationSensor(BaseSncbSensor):
    """Next station."""

    _attr_name = "Prochaine gare"
    _attr_icon = "mdi:map-marker-path"

    def __init__(self, coordinator: SncbTrainCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_next_station"

    @property
    def native_value(self) -> str | None:
        return self._data.get("next_station")


class NextDelaySensor(BaseSncbSensor):
    """Delay at next station."""

    _attr_name = "Retard prochaine gare"
    _attr_icon = "mdi:clock-fast"
    _attr_native_unit_of_measurement = "min"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: SncbTrainCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_next_delay"

    @property
    def native_value(self) -> int | None:
        return self._data.get("next_delay_minutes")


class DelayFromSensor(BaseSncbSensor):
    """Arrival delay at configured from station."""

    _attr_icon = "mdi:clock-alert-outline"
    _attr_native_unit_of_measurement = "min"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: SncbTrainCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_delay_from"
        self._attr_name = f"Retard arrivée {coordinator.station_from.title()}"

    @property
    def native_value(self) -> int | None:
        return self._data.get("delay_from_minutes")

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "scheduled": self._data.get("scheduled_from"),
            "platform": self._data.get("platform_from"),
        }


class DelayToSensor(BaseSncbSensor):
    """Arrival delay at configured to station."""

    _attr_icon = "mdi:clock-alert"
    _attr_native_unit_of_measurement = "min"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: SncbTrainCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_delay_to"
        self._attr_name = f"Retard arrivée {coordinator.station_to.title()}"

    @property
    def native_value(self) -> int | None:
        return self._data.get("delay_to_minutes")

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "scheduled": self._data.get("scheduled_to"),
            "platform": self._data.get("platform_to"),
        }


class PlatformFromSensor(BaseSncbSensor):
    """Platform at from station."""

    _attr_icon = "mdi:railroad-light"

    def __init__(self, coordinator: SncbTrainCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_platform_from"
        self._attr_name = f"Quai {coordinator.station_from.title()}"

    @property
    def native_value(self) -> str | None:
        return self._data.get("platform_from")


class PlatformToSensor(BaseSncbSensor):
    """Platform at to station."""

    _attr_icon = "mdi:railroad-light"

    def __init__(self, coordinator: SncbTrainCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_platform_to"
        self._attr_name = f"Quai {coordinator.station_to.title()}"

    @property
    def native_value(self) -> str | None:
        return self._data.get("platform_to")
