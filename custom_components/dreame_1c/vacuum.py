"""Vacuum entity for the Dreame 1C."""
from __future__ import annotations

from typing import Any

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    ACTION_LOCATE,
    ACTION_RETURN_HOME,
    ACTION_START_SWEEP,
    ACTION_STOP_CLEAN,
    ACTION_STOP_SWEEP,
    CHARGING_STATES,
    FAN_BY_NAME,
    FAN_SPEEDS,
    STATUS_MOPPING,
    WATER_BY_NAME,
)
from .coordinator import Dreame1CConfigEntry, Dreame1CCoordinator
from .entity import Dreame1CEntity

PARALLEL_UPDATES = 0  # the coordinator serialises robot access

# vacuum-card shows the `status` attribute and translates its own keys; it has
# no "mopping" key, so that one is sent as text in the instance language.
MOPPING_TEXT = {"pt": "Passando pano", "en": "Mopping"}

ACTIVITY = {
    1: VacuumActivity.CLEANING,
    2: VacuumActivity.IDLE,
    3: VacuumActivity.PAUSED,
    4: VacuumActivity.ERROR,
    5: VacuumActivity.RETURNING,
    6: VacuumActivity.DOCKED,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Dreame1CConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([Dreame1CVacuum(entry.runtime_data)])


class Dreame1CVacuum(Dreame1CEntity, StateVacuumEntity):
    _attr_name = None  # the device name
    _attr_fan_speed_list = list(FAN_BY_NAME)
    _attr_supported_features = (
        VacuumEntityFeature.STATE
        | VacuumEntityFeature.START
        | VacuumEntityFeature.STOP
        | VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.LOCATE
        | VacuumEntityFeature.FAN_SPEED
    )

    def __init__(self, coordinator: Dreame1CCoordinator) -> None:
        super().__init__(coordinator, "vacuum")

    @property
    def activity(self) -> VacuumActivity | None:
        status = self._value("status")
        if status == 2 and self._value("charging_state") in CHARGING_STATES:
            return VacuumActivity.DOCKED
        return ACTIVITY.get(status)

    @property
    def fan_speed(self) -> str | None:
        return FAN_SPEEDS.get(self._value("fan_speed"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            # vacuum-card reads battery and status from these attributes
            "battery_level": self._value("battery"),
            "status": self._card_status(),
            "cleaning_mode": "mopping" if self.coordinator.water_tank else "vacuuming",
            # rooms of a room clean started from HA (the robot doesn't report them)
            "cleaning_rooms": self.coordinator.active_room_names,
            "work_mode": self._value("work_mode"),
            "rooms": {str(k): v for k, v in self.coordinator.rooms.items()},
        }

    def _card_status(self) -> str | None:
        status = self.coordinator.status
        if status == STATUS_MOPPING:
            language = self.hass.config.language.split("-")[0]
            return MOPPING_TEXT.get(language, MOPPING_TEXT["en"])
        if self.activity == VacuumActivity.DOCKED:
            return "docked"
        return status

    async def async_start(self) -> None:
        # start-sweep: full clean, or resume when paused
        await self.coordinator.async_action(ACTION_START_SWEEP)

    async def async_pause(self) -> None:
        # stop-sweeping (3.2) leaves the robot in status 3 (paused); 18.2 ends the job
        await self.coordinator.async_action(ACTION_STOP_SWEEP)

    async def async_stop(self, **kwargs: Any) -> None:
        await self.coordinator.async_action(ACTION_STOP_CLEAN)

    async def async_return_to_base(self, **kwargs: Any) -> None:
        await self.coordinator.async_action(ACTION_RETURN_HOME)

    async def async_locate(self, **kwargs: Any) -> None:
        await self.coordinator.async_action(ACTION_LOCATE)

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        await self.coordinator.async_set("fan_speed", FAN_BY_NAME[fan_speed])

    async def async_clean_rooms(
        self,
        rooms: list[str],
        repeats: int = 1,
        fan_speed: str | None = None,
        water_level: str | None = None,
    ) -> None:
        """dreame_1c.clean_rooms: rooms by id or configured name."""
        await self.coordinator.async_clean_rooms(
            self.coordinator.resolve_rooms(rooms),
            repeats,
            FAN_BY_NAME[fan_speed] if fan_speed else None,
            WATER_BY_NAME[water_level] if water_level else None,
        )
