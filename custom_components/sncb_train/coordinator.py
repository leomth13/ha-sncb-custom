"""DataUpdateCoordinator for SNCB Train Tracker."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
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
        self._had_live_data_today = False
        self._last_good_data: dict[str, Any] | None = None

        if not vehicle_id.upper().startswith("BE.NMBS."):
            self.api_vehicle_id = f"BE.NMBS.{vehicle_id.upper().replace(' ', '')}"
        else:
            self.api_vehicle_id = vehicle_id.upper()

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from iRail vehicle endpoint.

        Never raises on first failure if we can return a structured empty payload,
        so sensors stay available.
        """
        url = f"{API_VEHICLE}?id={self.api_vehicle_id}&format=json&lang=fr"
        session = async_get_clientsession(self.hass)

        try:
            async with session.get(
                url,
                timeout=15,
                headers={"User-Agent": "HomeAssistant-SNCB-Train/1.2.2"},
            ) as response:
                status = response.status
                text = await response.text()

                if status in (502, 503, 504):
                    _LOGGER.warning(
                        "iRail temporary error %s for %s",
                        status,
                        self.api_vehicle_id,
                    )
                    return self._keep_or_empty("temporary_error", f"http_{status}")

                if status == 404:
                    return self._handle_not_found()

                if status != 200:
                    _LOGGER.warning(
                        "iRail HTTP %s for %s: %s",
                        status,
                        self.api_vehicle_id,
                        text[:200],
                    )
                    return self._keep_or_empty("temporary_error", f"http_{status}")

                # Parse JSON
                try:
                    import json

                    data = json.loads(text)
                except Exception as err:
                    _LOGGER.warning("Invalid JSON from iRail for %s: %s", self.api_vehicle_id, err)
                    return self._keep_or_empty("temporary_error", "invalid_json")

                # iRail sometimes returns 200 with an exception payload
                if isinstance(data, dict) and data.get("exception"):
                    _LOGGER.info(
                        "Journey not found for %s: %s",
                        self.api_vehicle_id,
                        data.get("message", data.get("exception")),
                    )
                    return self._handle_not_found()

                parsed = self._parse_vehicle(data)

                if parsed.get("status") not in (
                    "not_found",
                    "no_stops",
                    "temporary_error",
                    "data_lost",
                ):
                    self._had_live_data_today = True
                    self._last_good_data = parsed

                return parsed

        except Exception as err:
            _LOGGER.warning(
                "Error fetching %s: %s – keeping last data if any",
                self.api_vehicle_id,
                err,
            )
            return self._keep_or_empty("temporary_error", "exception")

    def _keep_or_empty(self, status: str, warning: str | None = None) -> dict[str, Any]:
        """Return last good data or empty structure."""
        if self._last_good_data:
            data = dict(self._last_good_data)
            data["api_warning"] = warning
            data["last_update"] = dt_util.now().isoformat()
            return data
        return self._empty_data(status, warning)

    def _handle_not_found(self) -> dict[str, Any]:
        """Handle journey not found more gracefully."""
        if self._had_live_data_today and self._last_good_data:
            _LOGGER.info(
                "Journey %s no longer found – keeping last state",
                self.api_vehicle_id,
            )
            data = dict(self._last_good_data)
            if data.get("left_to"):
                data["status"] = "passed"
            else:
                data["status"] = "data_lost"
            data["api_warning"] = "journey_not_found"
            data["last_update"] = dt_util.now().isoformat()
            return data
        return self._empty_data("not_found")

    def _empty_data(
        self, status: str = "not_found", warning: str | None = None
    ) -> dict[str, Any]:
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
            "current_delay_minutes": None,
            "next_station": None,
            "next_delay_minutes": None,
            "occupancy": None,
            "canceled": False,
            "left_from": False,
            "arrived_from": False,
            "left_to": False,
            "arrived_to": False,
            "api_warning": warning,
            "last_update": dt_util.now().isoformat(),
        }

    def _find_stop(self, stops: list, station_name: str) -> dict | None:
        """Find a stop by station name (partial match)."""
        for stop in stops:
            if not isinstance(stop, dict):
                continue
            name = (stop.get("station") or "").lower()
            standard = (stop.get("stationinfo", {}) or {}).get("standardname") or ""
            standard = standard.lower()
            if station_name in name or station_name in standard:
                return stop
        return None

    def _get_arrival_delay_minutes(self, stop: dict | None) -> int | None:
        """Extract arrival delay in minutes from a stop."""
        if not stop:
            return None
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
            return (
                datetime.fromtimestamp(int(ts), tz=timezone.utc)
                .astimezone()
                .strftime("%H:%M")
            )
        except (ValueError, TypeError):
            return None

    def _normalize_stops(self, stops_raw) -> list:
        """Ensure stops is always a list of dicts."""
        if stops_raw is None:
            return []
        if isinstance(stops_raw, dict):
            # Single stop returned as object instead of list
            return [stops_raw]
        if isinstance(stops_raw, list):
            return [s for s in stops_raw if isinstance(s, dict)]
        return []

    def _parse_vehicle(self, data: dict) -> dict[str, Any]:
        """Parse the vehicle JSON focusing on monitored stations + current/next."""
        if not isinstance(data, dict):
            return self._empty_data("no_stops")

        vehicle_info = data.get("vehicleinfo") or {}
        stops_container = data.get("stops") or {}
        stops = self._normalize_stops(stops_container.get("stop"))

        if not stops:
            return self._empty_data("no_stops")

        stop_from = self._find_stop(stops, self.station_from)
        stop_to = self._find_stop(stops, self.station_to)

        # --- Current & next station ---
        current_station = None
        current_delay = None
        next_station = None
        next_delay = None
        current_idx = -1

        for i, stop in enumerate(stops):
            if str(stop.get("left", "0")) == "1":
                current_idx = i
                current_station = stop.get("station")
                current_delay = self._get_arrival_delay_minutes(stop)

        if current_idx == -1:
            current_station = stops[0].get("station")
            current_delay = self._get_arrival_delay_minutes(stops[0])

        start_search = current_idx + 1 if current_idx >= 0 else 0
        for stop in stops[start_search:]:
            if str(stop.get("left", "0")) == "0":
                next_station = stop.get("station")
                next_delay = self._get_arrival_delay_minutes(stop)
                break

        delay_from = self._get_arrival_delay_minutes(stop_from)
        delay_to = self._get_arrival_delay_minutes(stop_to)

        platform_from = stop_from.get("platform") if stop_from else None
        platform_to = stop_to.get("platform") if stop_to else None

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

        canceled = False
        left_from = arrived_from = left_to = arrived_to = False
        occupancy = "unknown"

        if stop_from:
            canceled = str(stop_from.get("canceled", "0")) == "1"
            left_from = str(stop_from.get("left", "0")) == "1"
            arrived_from = str(stop_from.get("arrived", "0")) == "1"
            occ = stop_from.get("occupancy") or {}
            if isinstance(occ, dict):
                occupancy = occ.get("name", "unknown")

        if stop_to:
            left_to = str(stop_to.get("left", "0")) == "1"
            arrived_to = str(stop_to.get("arrived", "0")) == "1"
            if str(stop_to.get("canceled", "0")) == "1":
                canceled = True

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
            first_left = str(stops[0].get("left", "0")) == "1"
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
            "current_delay_minutes": current_delay,
            "next_station": next_station,
            "next_delay_minutes": next_delay,
            "occupancy": occupancy,
            "canceled": canceled,
            "left_from": left_from,
            "arrived_from": arrived_from,
            "left_to": left_to,
            "arrived_to": arrived_to,
            "api_warning": None,
            "last_update": dt_util.now().isoformat(),
        }
