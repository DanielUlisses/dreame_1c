"""Base entity for the Dreame 1C."""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MODEL
from .coordinator import Dreame1CCoordinator


class Dreame1CEntity(CoordinatorEntity[Dreame1CCoordinator]):
    """One device per config entry; unique ids are '<entry unique_id>_<key>'."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: Dreame1CCoordinator, key: str) -> None:
        super().__init__(coordinator)
        uid = coordinator.config_entry.unique_id or coordinator.config_entry.entry_id
        self._attr_unique_id = f"{uid}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, uid)},
            manufacturer="Dreame",
            name="Dreame 1C",
            model="Mi Robot Vacuum-Mop 2C",
            model_id=MODEL,
            sw_version=coordinator.firmware,
        )

    def _value(self, prop: str) -> Any:
        return (self.coordinator.data or {}).get(prop)
