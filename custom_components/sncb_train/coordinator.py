"""DataUpdateCoordinator for SNCB Train Tracker."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import API_VEHICLE, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class SncbTrainCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that polls the iRail vehicle endpoint."""

    def __init__(
        self,
        hass: HomeAssistant,
        vehicle_id: str,
        station_from: str,
        station_to: str,
        name: str,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"SNCB {name}",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.vehicle_id = vehicle_id
        self.station_from = station_from.lower()
        self.station_to = station_to.lower()
        self.friendly_name = name

        if not vehicle_id.upper().startswith("BE.NMBS."):
            self.api_vehicle_id = f"BE.NMBS.{vehicle_id.upper().replace(' ', '')}"
        else:
            self.api_vehicle_id = vehicle_id.upper()

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from iRail vehicle endpoint."""
        url = f"{API_VEHICLE}?id={self.api_vehicle_id}&format=json&lang=fr"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=15),
                    headers={"User-Agent": "HomeAssistant-SNCB-Train/1.1"},
                ) as response:
                    if response.status == 404:
                        return self._empty_data("not_found")
                    if response.status != 200:
                        text = await response.text()
                        raise UpdateFailed(f"API error {response.status}: {text[:200]}")

                    data = await response.json()

        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error communicating with iRail: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error: {err}") from err

        return self._parse_vehicle(data)

    def _empty_data(self, status: str = "not_found") -> dict[str, Any]:
        """Return empty structure when train is not running today."""
        return {
            "status": status,
            "vehicle": self.api_vehicle_id,
            "shortname": self.friendly_name,
            "delay_from_minutes": None,
            "delay_to_minutes": None,
            "platform_from": None,
            "platform_to": None,
            "scheduled_from": None,
            "scheduled_to": None,
            "current_station": None,
            "occupancy": None,
            "canceled": False,
            "left_from": False,
            "arrived_from": False,
            "left_to": False,
            "arrived_to": False,
            "last_update": dt_util.now().isoformat(),
        }

    def _find_stop(self, stops: list, station_name: str) -> dict | None:
        """Find a stop by station name (partial match)."""
        for stop in stops:
            name = (stop.get("station") or "").lower()
            standard = (stop.get("stationinfo", {}).get("standardname") or "").lower()
            if station_name in name or station_name in standard:
                return stop
        return None

    def _get_arrival_delay_minutes(self, stop: dict | None) -> int | None:
        """Extract arrival delay in minutes from a stop."""
        if not stop:
            return None
        # Prefer arrivalDelay, fallback to delay
        delay_sec = stop.get("arrivalDelay")
        if delay_sec is None:
            delay_sec = stop.get("delay")
        try:
            return round(int(delay_sec or 0) / 60)
        except (ValueError, TypeError):
            return 0

    def _format_time(self, ts) -> str | None:
        """Convert unix timestamp to HH:MM local time."""
        if not ts:
            return None
        try:
            return datetime.fromtimestamp(int(ts), tz=timezone.utc).astimezone().strftime("%H:%M")
        except (ValueError, TypeError):
            return None

    def _parse_vehicle(self, data: dict) -> dict[str, Any]:
        """Parse the vehicle JSON focusing on the two monitored stations."""
        vehicle_info = data.get("vehicleinfo", {})
        stops = data.get("stops", {}).get("stop", [])

        if not stops:
            return self._empty_data("no_stops")

        stop_from = self._find_stop(stops, self.station_from)
        stop_to = self._find_stop(stops, self.station_to)

        # Current position = last stop that has already left
        current_station = None
        for stop in reversed(stops):
            if str(stop.get("left", "0")) == "1":
                current_station = stop.get("station")
                break
        if current_station is None and stops:
            current_station = stops[0].get("station")

        # Delays (arrival)
        delay_from = self._get_arrival_delay_minutes(stop_from)
        delay_to = self._get_arrival_delay_minutes(stop_to)

        # Platforms
        platform_from = stop_from.get("platform") if stop_from else None
        platform_to = stop_to.get("platform") if stop_to else None

        # Scheduled times
        scheduled_from = None
        if stop_from:
            scheduled_from = self._format_time(
                stop_from.get("scheduledArrivalTime")
                or stop_from.get("scheduledDepartureTime")
                or stop_from.get("time")
            )
        scheduled_to = None
        if stop_to:
            scheduled_to = self._format_time(
                stop_to.get("scheduledArrivalTime") or stop_to.get("time")
            )

        # Flags
        canceled = False
        left_from = arrived_from = left_to = arrived_to = False
        occupancy = "unknown"

        if stop_from:
            canceled = str(stop_from.get("canceled", "0")) == "1"
            left_from = str(stop_from.get("left", "0")) == "1"
            arrived_from = str(stop_from.get("arrived", "0")) == "1"
            occ = stop_from.get("occupancy", {})
            occupancy = occ.get("name", "unknown") if isinstance(occ, dict) else "unknown"

        if stop_to:
            left_to = str(stop_to.get("left", "0")) == "1"
            arrived_to = str(stop_to.get("arrived", "0")) == "1"
            if str(stop_to.get("canceled", "0")) == "1":
                canceled = True

        # Status logic
        if canceled:
            status = "canceled"
        elif stop_from is None and stop_to is None:
            status = "station_not_found"
        elif left_to:
            status = "passed"
        elif arrived_to:
            status = "at_destination"
        elif left_from:
            status = "en_route"
        elif arrived_from:
            status = "at_departure"
        else:
            first_left = str(stops[0].get("left", "0")) == "1" if stops else False
            status = "en_route" if first_left else "not_departed"

        return {
            "status": status,
            "vehicle": data.get("vehicle") or self.api_vehicle_id,
            "shortname": vehicle_info.get("shortname") or self.friendly_name,
            "delay_from_minutes": delay_from,
            "delay_to_minutes": delay_to,
            "platform_from": platform_from,
            "platform_to": platform_to,
            "scheduled_from": scheduled_from,
            "scheduled_to": scheduled_to,
            "current_station": current_station,
            "occupancy": occupancy,
            "canceled": canceled,
            "left_from": left_from,
            "arrived_from": arrived_from,
            "left_to": left_to,
            "arrived_to": arrived_to,
            "last_update": dt_util.now().isoformat(),
        }
