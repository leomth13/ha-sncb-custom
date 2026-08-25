"""DataUpdateCoordinator for SNCB Train Tracker."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from aiohttp import ClientTimeout
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import API_VEHICLE, DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class SncbTrainCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls the iRail vehicle endpoint for one train."""

    def __init__(
        self,
        hass: HomeAssistant,
        vehicle_id: str,
        station_from: str,
        station_to: str,
        name: str,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"SNCB {name}",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.vehicle_id = vehicle_id
        self.station_from = station_from.lower().strip()
        self.station_to = station_to.lower().strip()
        self.friendly_name = name
        self._had_live_data_today = False
        self._last_good_data: dict[str, Any] | None = None

        clean = vehicle_id.upper().replace(" ", "")
        if clean.startswith("BE.NMBS."):
            self.api_vehicle_id = clean
        else:
            self.api_vehicle_id = f"BE.NMBS.{clean}"

        _LOGGER.warning(
            "Coordinator ready: %s (%s -> %s)",
            self.api_vehicle_id,
            self.station_from,
            self.station_to,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch vehicle data. Always returns a dict (never raises)."""
        url = f"{API_VEHICLE}?id={self.api_vehicle_id}&format=json&lang=fr"
        session = async_get_clientsession(self.hass)
        timeout = ClientTimeout(total=25)

        for attempt in range(3):
            try:
                async with session.get(
                    url,
                    timeout=timeout,
                    headers={"User-Agent": "HomeAssistant-SNCB-Train/1.3.0"},
                ) as response:
                    status = response.status
                    body = await response.text()

                    if status in (502, 503, 504):
                        _LOGGER.warning(
                            "iRail HTTP %s for %s (try %s/3)",
                            status,
                            self.api_vehicle_id,
                            attempt + 1,
                        )
                        if attempt < 2:
                            await asyncio.sleep(2 * (attempt + 1))
                            continue
                        return self._fallback("temporary_error", f"http_{status}")

                    if status == 404:
                        return self._handle_not_found()

                    if status != 200:
                        _LOGGER.warning(
                            "iRail HTTP %s for %s: %s",
                            status,
                            self.api_vehicle_id,
                            body[:120],
                        )
                        return self._fallback("temporary_error", f"http_{status}")

                    try:
                        payload = json.loads(body)
                    except Exception as err:
                        _LOGGER.warning("Bad JSON for %s: %s", self.api_vehicle_id, err)
                        return self._fallback("temporary_error", "invalid_json")

                    if isinstance(payload, dict) and payload.get("exception"):
                        _LOGGER.info(
                            "No journey for %s: %s",
                            self.api_vehicle_id,
                            payload.get("message", payload.get("exception")),
                        )
                        return self._handle_not_found()

                    parsed = self._parse(payload)
                    _LOGGER.warning(
                        "%s status=%s pos=%s next=%s d_from=%s d_to=%s",
                        self.api_vehicle_id,
                        parsed.get("status"),
                        parsed.get("current_station"),
                        parsed.get("next_station"),
                        parsed.get("delay_from_minutes"),
                        parsed.get("delay_to_minutes"),
                    )

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
                    "Fetch error %s try %s/3: %s: %s",
                    self.api_vehicle_id,
                    attempt + 1,
                    type(err).__name__,
                    err,
                )
                if attempt < 2:
                    await asyncio.sleep(2 * (attempt + 1))
                    continue
                return self._fallback("temporary_error", "exception")

        return self._fallback("temporary_error", "retries_exhausted")

    def _fallback(self, status: str, warning: str | None = None) -> dict[str, Any]:
        if self._last_good_data:
            data = dict(self._last_good_data)
            data["api_warning"] = warning
            data["last_update"] = dt_util.now().isoformat()
            return data
        return self._empty(status, warning)

    def _handle_not_found(self) -> dict[str, Any]:
        if self._had_live_data_today and self._last_good_data:
            data = dict(self._last_good_data)
            data["status"] = "passed" if data.get("left_to") else "data_lost"
            data["api_warning"] = "journey_not_found"
            data["last_update"] = dt_util.now().isoformat()
            return data
        return self._empty("not_found")

    def _empty(self, status: str = "not_found", warning: str | None = None) -> dict[str, Any]:
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
            "canceled": False,
            "left_from": False,
            "left_to": False,
            "arrived_from": False,
            "api_warning": warning,
            "last_update": dt_util.now().isoformat(),
        }

    @staticmethod
    def _normalize_stops(raw) -> list[dict]:
        if raw is None:
            return []
        if isinstance(raw, dict):
            return [raw]
        if isinstance(raw, list):
            return [s for s in raw if isinstance(s, dict)]
        return []

    def _find_stop(self, stops: list[dict], station_name: str) -> dict | None:
        for stop in stops:
            name = (stop.get("station") or "").lower()
            info = stop.get("stationinfo") or {}
            standard = (info.get("standardname") or "").lower()
            if station_name in name or station_name in standard:
                return stop
        return None

    @staticmethod
    def _arrival_delay_min(stop: dict | None) -> int | None:
        if not stop:
            return None
        raw = stop.get("arrivalDelay")
        if raw is None:
            raw = stop.get("delay")
        try:
            return round(int(raw or 0) / 60)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _fmt_time(ts) -> str | None:
        if not ts:
            return None
        try:
            return (
                datetime.fromtimestamp(int(ts), tz=timezone.utc)
                .astimezone()
                .strftime("%H:%M")
            )
        except (TypeError, ValueError):
            return None

    def _parse(self, data: dict) -> dict[str, Any]:
        if not isinstance(data, dict):
            return self._empty("no_stops")

        vehicle_info = data.get("vehicleinfo") or {}
        stops = self._normalize_stops((data.get("stops") or {}).get("stop"))
        if not stops:
            return self._empty("no_stops")

        stop_from = self._find_stop(stops, self.station_from)
        stop_to = self._find_stop(stops, self.station_to)

        current_station = None
        current_delay = None
        next_station = None
        next_delay = None
        current_idx = -1

        for i, stop in enumerate(stops):
            if str(stop.get("left", "0")) == "1":
                current_idx = i
                current_station = stop.get("station")
                current_delay = self._arrival_delay_min(stop)

        if current_idx < 0:
            current_station = stops[0].get("station")
            current_delay = self._arrival_delay_min(stops[0])
            if len(stops) > 1:
                next_station = stops[1].get("station")
                next_delay = self._arrival_delay_min(stops[1])
        else:
            for stop in stops[current_idx + 1 :]:
                if str(stop.get("left", "0")) == "0":
                    next_station = stop.get("station")
                    next_delay = self._arrival_delay_min(stop)
                    break

        delay_from = self._arrival_delay_min(stop_from)
        delay_to = self._arrival_delay_min(stop_to)
        platform_from = stop_from.get("platform") if stop_from else None
        platform_to = stop_to.get("platform") if stop_to else None

        scheduled_from = None
        if stop_from:
            scheduled_from = self._fmt_time(
                stop_from.get("scheduledArrivalTime")
                or stop_from.get("scheduledDepartureTime")
                or stop_from.get("time")
            )
        scheduled_to = None
        if stop_to:
            scheduled_to = self._fmt_time(
                stop_to.get("scheduledArrivalTime") or stop_to.get("time")
            )

        canceled = False
        left_from = left_to = False
        arrived_from = False
        if stop_from:
            canceled = str(stop_from.get("canceled", "0")) == "1"
            left_from = str(stop_from.get("left", "0")) == "1"
            arrived_from = str(stop_from.get("arrived", "0")) == "1"
        if stop_to:
            left_to = str(stop_to.get("left", "0")) == "1"
            if str(stop_to.get("canceled", "0")) == "1":
                canceled = True

        if canceled:
            status = "canceled"
        elif stop_from is None and stop_to is None:
            status = "station_not_found"
        elif left_to:
            status = "passed"
        elif left_from:
            status = "en_route"
        elif str(stops[0].get("left", "0")) == "1":
            status = "en_route"
        else:
            status = "not_departed"

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
            "canceled": canceled,
            "left_from": left_from,
            "left_to": left_to,
            "arrived_from": arrived_from,
            "api_warning": None,
            "last_update": dt_util.now().isoformat(),
        }
