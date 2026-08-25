"""Config flow for SNCB Train Tracker."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_NAME,
    CONF_STATION_FROM,
    CONF_STATION_TO,
    CONF_VEHICLE_ID,
    DEFAULT_STATION_FROM,
    DEFAULT_STATION_TO,
    DOMAIN,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_VEHICLE_ID): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
        ),
        vol.Required(CONF_STATION_FROM, default=DEFAULT_STATION_FROM): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
        ),
        vol.Required(CONF_STATION_TO, default=DEFAULT_STATION_TO): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
        ),
        vol.Optional(CONF_NAME): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
        ),
    }
)


class SncbTrainConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SNCB Train Tracker."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            vehicle_id = user_input[CONF_VEHICLE_ID].strip().upper()
            clean_id = vehicle_id.replace("BE.NMBS.", "").replace(" ", "")

            await self.async_set_unique_id(clean_id)
            self._abort_if_unique_id_configured()

            name = user_input.get(CONF_NAME) or clean_id

            return self.async_create_entry(
                title=name,
                data={
                    CONF_VEHICLE_ID: clean_id,
                    CONF_STATION_FROM: user_input[CONF_STATION_FROM].strip(),
                    CONF_STATION_TO: user_input[CONF_STATION_TO].strip(),
                    CONF_NAME: name,
                },
            )

        return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA)
