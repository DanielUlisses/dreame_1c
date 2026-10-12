"""Mop water level select for the Dreame 1C."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import WATER_BY_NAME, WATER_LEVELS
from .coordinator import Dreame1CConfigEntry, Dreame1CCoordinator
from .entity import Dreame1CEntity

PARALLEL_UPDATES = 0  # the coordinator serialises robot access


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Dreame1CConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([Dreame1CWaterLevel(entry.runtime_data)])


class Dreame1CWaterLevel(Dreame1CEntity, SelectEntity):
    _attr_translation_key = "water_level"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = list(WATER_BY_NAME)

    def __init__(self, coordinator: Dreame1CCoordinator) -> None:
        super().__init__(coordinator, "water_level")

    @property
    def current_option(self) -> str | None:
        return WATER_LEVELS.get(self._value("water_level"))

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set("water_level", WATER_BY_NAME[option])
