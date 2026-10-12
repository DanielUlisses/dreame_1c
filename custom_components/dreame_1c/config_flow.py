"""Config and options flow for the Dreame 1C."""
from __future__ import annotations

import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import callback
from homeassistant.helpers import selector

from .api import DreameClient, DreameError
from .const import (
    CONF_ROOMS,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PROPS,
    parse_rooms,
)

TOKEN_RE = re.compile(r"^[0-9a-fA-F]{32}$")


def _schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
            vol.Required(CONF_TOKEN, default=defaults.get(CONF_TOKEN, "")): str,
        }
    )


def _probe(host: str, token: str) -> int:
    """Blocking: read the battery level (2.1) and return the miio device id."""
    client = DreameClient(host, token)
    if client.get_props({"battery": PROPS["battery"]})["battery"] is None:
        raise DreameError("battery level not readable")
    return client.device_id


class Dreame1CConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _validate(
        self, user_input: dict[str, Any], errors: dict[str, str]
    ) -> int | None:
        user_input[CONF_HOST] = user_input[CONF_HOST].strip()
        user_input[CONF_TOKEN] = user_input[CONF_TOKEN].strip().lower()
        if not TOKEN_RE.match(user_input[CONF_TOKEN]):
            errors[CONF_TOKEN] = "invalid_token"
            return None
        try:
            return await self.hass.async_add_executor_job(
                _probe, user_input[CONF_HOST], user_input[CONF_TOKEN]
            )
        except DreameError:
            errors["base"] = "cannot_connect"
            return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            device_id = await self._validate(user_input, errors)
            if device_id is not None:
                # miio device id; fall back to the host if the handshake gave none
                await self.async_set_unique_id(str(device_id or user_input[CONF_HOST]))
                self._abort_if_unique_id_configured(updates=user_input)
                return self.async_create_entry(
                    title=f"Dreame 1C ({user_input[CONF_HOST]})",
                    data=user_input,
                    options={CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL, CONF_ROOMS: ""},
                )
        return self.async_show_form(
            step_id="user", data_schema=_schema(user_input or {}), errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """New IP or new token (the token changes whenever the robot is re-paired)."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            device_id = await self._validate(user_input, errors)
            if device_id is not None:
                # Same robot only: a different device id means wrong IP/token.
                await self.async_set_unique_id(str(device_id or user_input[CONF_HOST]))
                self._abort_if_unique_id_mismatch(reason="wrong_device")
                return self.async_update_reload_and_abort(entry, data_updates=user_input)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_schema(user_input or dict(entry.data)),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> Dreame1COptionsFlow:
        return Dreame1COptionsFlow()


class Dreame1COptionsFlow(OptionsFlow):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                parse_rooms(user_input.get(CONF_ROOMS, ""))
            except ValueError:
                errors[CONF_ROOMS] = "invalid_rooms"
            else:
                user_input[CONF_SCAN_INTERVAL] = int(user_input[CONF_SCAN_INTERVAL])
                return self.async_create_entry(data=user_input)

        current = user_input or self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_ROOMS, default=current.get(CONF_ROOMS, "")
                    ): selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=5,
                            max=300,
                            step=1,
                            unit_of_measurement="s",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
            errors=errors,
        )
