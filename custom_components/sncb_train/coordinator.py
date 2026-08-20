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
        station: str,
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
        self.station = station.lower()
        self.friendly_name = name

        # Normalize vehicle id
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
                    headers={"User-Agent": "HomeAssistant-SNCB-Train/1.0"},
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
            "delay_minutes": None,
            "platform": None,
            "current_station": None,
            "occupancy": None,
            "scheduled_time": None,
            "canceled": False,
            "left_station": False,
            "arrived_station": False,
            "last_update": dt_util.now().isoformat(),
            "raw_stops": [],
        }

    def _parse_vehicle(self, data: dict) -> dict[str, Any]:
        """Parse the vehicle JSON into a clean dict focused on the monitored station."""
        vehicle_info = data.get("vehicleinfo", {})
        stops = data.get("stops", {}).get("stop", [])

        if not stops:
            return self._empty_data("no_stops")

        # Find the monitored station stop
        target_stop = None
        for stop in stops:
            station_name = (stop.get("station") or "").lower()
            standard = (stop.get("stationinfo", {}).get("standardname") or "").lower()
            if self.station in station_name or self.station in standard:
                target_stop = stop
                break

        # Determine current position: last stop that has already left
        current_station = None
        for stop in reversed(stops):
            if str(stop.get("left", "0")) == "1":
                current_station = stop.get("station")
                break
        if current_station is None:
            # Train has not left the first station yet
            current_station = stops[0].get("station") if stops else None

        # Extract data for the monitored station
        delay_seconds = 0
        platform = None
        scheduled_ts = None
        canceled = False
        left_station = False
        arrived_station = False
        occupancy = "unknown"

        if target_stop:
            delay_seconds = int(target_stop.get("delay") or target_stop.get("departureDelay") or 0)
            platform = target_stop.get("platform")
            scheduled_ts = target_stop.get("scheduledDepartureTime") or target_stop.get("time")
            canceled = str(target_stop.get("canceled", "0")) == "1"
            left_station = str(target_stop.get("left", "0")) == "1"
            arrived_station = str(target_stop.get("arrived", "0")) == "1"
            occ = target_stop.get("occupancy", {})
            occupancy = occ.get("name", "unknown") if isinstance(occ, dict) else "unknown"

        delay_minutes = round(delay_seconds / 60) if delay_seconds else 0

        # Build status
        if canceled:
            status = "canceled"
        elif target_stop is None:
            status = "station_not_found"
        elif left_station:
            status = "passed"
        elif arrived_station:
            status = "at_station"
        elif current_station and self.station in (current_station or "").lower():
            status = "at_station"
        else:
            # Check if train has started
            first_left = str(stops[0].get("left", "0")) == "1" if stops else False
            if not first_left:
                status = "not_departed"
            else:
                status = "en_route"

        scheduled_time = None
        if scheduled_ts:
            try:
                scheduled_time = datetime.fromtimestamp(
                    int(scheduled_ts), tz=timezone.utc
                ).astimezone().strftime("%H:%M")
            except (ValueError, TypeError):
                scheduled_time = None

        return {
            "status": status,
            "vehicle": data.get("vehicle") or self.api_vehicle_id,
            "shortname": vehicle_info.get("shortname") or self.friendly_name,
            "delay_minutes": delay_minutes,
            "platform": platform,
            "current_station": current_station,
            "occupancy": occupancy,
            "scheduled_time": scheduled_time,
            "canceled": canceled,
            "left_station": left_station,
            "arrived_station": arrived_station,
            "last_update": dt_util.now().isoformat(),
            "raw_stops_count": len(stops),
        }
