"""Dreame 1C / Mi Robot Vacuum-Mop 2C (dreame.vacuum.md1808), 100% local over miio."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.typing import ConfigType

from .api import DreameClient
from .const import (
    ATTR_FAN_SPEED,
    ATTR_REPEATS,
    ATTR_ROOMS,
    ATTR_WATER_LEVEL,
    DOMAIN,
    FAN_BY_NAME,
    PLATFORMS,
    SERVICE_CLEAN_ROOMS,
    WATER_BY_NAME,
)
from .coordinator import Dreame1CConfigEntry, Dreame1CCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

CLEAN_ROOMS_SCHEMA = {
    vol.Required(ATTR_ROOMS): vol.All(cv.ensure_list, [cv.string], vol.Length(min=1)),
    vol.Optional(ATTR_FAN_SPEED): vol.In(list(FAN_BY_NAME)),
    vol.Optional(ATTR_WATER_LEVEL): vol.In(list(WATER_BY_NAME)),
    vol.Optional(ATTR_REPEATS, default=1): vol.All(vol.Coerce(int), vol.Range(min=1, max=3)),
}


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register dreame_1c.clean_rooms once, independent of config entries."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_CLEAN_ROOMS,
        entity_domain=VACUUM_DOMAIN,
        schema=CLEAN_ROOMS_SCHEMA,
        func="async_clean_rooms",
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: Dreame1CConfigEntry) -> bool:
    client = DreameClient(entry.data[CONF_HOST], entry.data[CONF_TOKEN])
    coordinator = Dreame1CCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: Dreame1CConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload(hass: HomeAssistant, entry: Dreame1CConfigEntry) -> None:
    """Options (rooms, scan interval) changed: rebuild everything."""
    await hass.config_entries.async_reload(entry.entry_id)
