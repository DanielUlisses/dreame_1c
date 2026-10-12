"""Water tank binary sensor for the Dreame 1C."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
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
    async_add_entities([Dreame1CWaterTank(entry.runtime_data)])


class Dreame1CWaterTank(Dreame1CEntity, BinarySensorEntity):
    """On while the water tank is fitted: the robot mops instead of only vacuuming."""

    _attr_translation_key = "water_tank"

    def __init__(self, coordinator: Dreame1CCoordinator) -> None:
        super().__init__(coordinator, "water_tank")

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.water_tank
