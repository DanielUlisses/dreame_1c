"""Do-not-disturb switch for the Dreame 1C."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import Dreame1CConfigEntry, Dreame1CCoordinator
from .entity import Dreame1CEntity

PARALLEL_UPDATES = 0  # the coordinator serialises robot access


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Dreame1CConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([Dreame1CDnd(entry.runtime_data)])


class Dreame1CDnd(Dreame1CEntity, SwitchEntity):
    _attr_translation_key = "dnd"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: Dreame1CCoordinator) -> None:
        super().__init__(coordinator, "dnd")

    @property
    def is_on(self) -> bool | None:
        value = self._value("dnd")
        return None if value is None else bool(value)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        # 20.2 / 20.3 as reported by the robot (window is edited in the Xiaomi app)
        return {"start": self._value("dnd_start"), "end": self._value("dnd_end")}

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set("dnd", True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set("dnd", False)
