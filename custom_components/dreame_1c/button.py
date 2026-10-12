"""Reset-consumable and per-room clean buttons for the Dreame 1C."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ACTION_RESET_FILTER, ACTION_RESET_MAIN_BRUSH, ACTION_RESET_SIDE_BRUSH
from .coordinator import Dreame1CConfigEntry, Dreame1CCoordinator
from .entity import Dreame1CEntity

PARALLEL_UPDATES = 0  # the coordinator serialises robot access

RESETS = {
    "reset_filter": ACTION_RESET_FILTER,
    "reset_main_brush": ACTION_RESET_MAIN_BRUSH,
    "reset_side_brush": ACTION_RESET_SIDE_BRUSH,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Dreame1CConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[ButtonEntity] = [
        Dreame1CResetButton(coordinator, key, action) for key, action in RESETS.items()
    ]
    rooms = [Dreame1CRoomButton(coordinator, rid, name) for rid, name in coordinator.rooms.items()]
    entities.extend(rooms)

    # Drop buttons of rooms that were removed from the options.
    keep = {b.unique_id for b in rooms}
    registry = er.async_get(hass)
    for reg in er.async_entries_for_config_entry(registry, entry.entry_id):
        if reg.domain == "button" and "_room_" in reg.unique_id and reg.unique_id not in keep:
            registry.async_remove(reg.entity_id)

    async_add_entities(entities)


class Dreame1CResetButton(Dreame1CEntity, ButtonEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator: Dreame1CCoordinator, key: str, action: tuple[int, int]
    ) -> None:
        super().__init__(coordinator, key)
        self._attr_translation_key = key
        self._action = action

    async def async_press(self) -> None:
        await self.coordinator.async_action(self._action)


class Dreame1CRoomButton(Dreame1CEntity, ButtonEntity):
    """'Clean <room>' ('Limpar <room>'): one pass, current suction / water level."""

    _attr_translation_key = "clean_room"

    def __init__(self, coordinator: Dreame1CCoordinator, room_id: int, name: str) -> None:
        super().__init__(coordinator, f"room_{room_id}")
        self._attr_translation_placeholders = {"room": name}
        self._room_id = room_id

    async def async_press(self) -> None:
        await self.coordinator.async_clean_rooms([self._room_id])
