"""Polling coordinator for the Dreame 1C."""
from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import DreameClient, DreameError
from .const import (
    CONF_ROOMS,
    CONF_SCAN_INTERVAL,
    DEFAULT_FAN,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WATER,
    DOMAIN,
    FAN_SPEEDS,
    FIRMWARE,
    PROPS,
    REFRESH_AFTER_COMMAND,
    STATUS,
    STATUS_CLEANING,
    STATUS_MOPPING,
    WORK_MODE_ROOM_CLEAN,
    WATER_LEVELS,
    parse_rooms,
)

_LOGGER = logging.getLogger(__name__)

ROOMS_GRACE = 30  # seconds

type Dreame1CConfigEntry = ConfigEntry[Dreame1CCoordinator]


class Dreame1CCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls all PROPS; also the single entry point for commands."""

    config_entry: Dreame1CConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: Dreame1CConfigEntry, client: DreameClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self.client = client
        self.firmware: str | None = None
        # Rooms of the last room clean started from HA; the robot doesn't report them.
        self.active_rooms: list[int] = []
        self._rooms_started = 0.0
        self._unsub_refresh: Callable[[], None] | None = None
        try:
            self.rooms: dict[int, str] = parse_rooms(entry.options.get(CONF_ROOMS))
        except ValueError:
            _LOGGER.warning("Ignoring malformed rooms option: %s", entry.options.get(CONF_ROOMS))
            self.rooms = {}

    async def _async_setup(self) -> None:
        try:
            info = await self._run(self.client.get_props, {"fw": FIRMWARE})
            self.firmware = info["fw"]
        except DreameError:
            pass  # cosmetic only

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self._run(self.client.get_props, PROPS)
        except DreameError as err:
            raise UpdateFailed(str(err)) from err
        # The room job is over once the robot stops room-cleaning (e.g. back on the dock).
        # (grace period: the robot takes a moment to switch to room-cleaning)
        if (
            data.get("work_mode") != WORK_MODE_ROOM_CLEAN
            and time.monotonic() - self._rooms_started > ROOMS_GRACE
        ):
            self.active_rooms = []
        return data

    async def _run(self, func: Callable[..., Any], *args: Any) -> Any:
        return await self.hass.async_add_executor_job(func, *args)

    async def async_command(self, func: Callable[..., Any], *args: Any) -> None:
        """Run a client command, raise a user-facing error on failure, re-poll soon."""
        try:
            await self._run(func, *args)
        except DreameError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(err)},
            ) from err

        # The robot takes a moment to reflect a command; re-poll shortly after.
        if self._unsub_refresh:
            self._unsub_refresh()
        self._unsub_refresh = async_call_later(
            self.hass, REFRESH_AFTER_COMMAND, self._delayed_refresh
        )

    async def _delayed_refresh(self, _now: Any) -> None:
        self._unsub_refresh = None
        await self.async_request_refresh()

    async def async_shutdown(self) -> None:
        if self._unsub_refresh:
            self._unsub_refresh()
            self._unsub_refresh = None
        await super().async_shutdown()

    async def async_action(self, action: tuple[int, int]) -> None:
        await self.async_command(self.client.action, *action)

    async def async_set(self, prop: str, value: Any) -> None:
        """Write a polled prop and reflect it optimistically."""
        await self.async_command(self.client.set_prop, *PROPS[prop], value)
        if self.data is not None:
            self.async_set_updated_data({**self.data, prop: value})

    async def async_clean_rooms(
        self,
        rooms: list[int],
        repeats: int = 1,
        fan: int | None = None,
        water: int | None = None,
    ) -> None:
        """Room clean; suction/water default to the robot's current settings."""
        if fan is None:
            fan = self._current("fan_speed", FAN_SPEEDS, DEFAULT_FAN)
        if water is None:
            water = self._current("water_level", WATER_LEVELS, DEFAULT_WATER)
        await self.async_command(self.client.clean_rooms, rooms, repeats, fan, water)
        self.active_rooms = list(rooms)
        self._rooms_started = time.monotonic()

    @property
    def active_room_names(self) -> str | None:
        """Configured names of the rooms being cleaned (started from HA), or None."""
        if not self.active_rooms:
            return None
        return ", ".join(self.rooms.get(rid, str(rid)) for rid in self.active_rooms)

    @property
    def water_tank(self) -> bool | None:
        """Water tank fitted (18.9): the robot mops instead of only vacuuming."""
        value = (self.data or {}).get("water_box")
        return None if value is None else value == 1

    @property
    def status(self) -> str | None:
        """STATUS key, with cleaning reported as 'mopping' while the tank is fitted."""
        status = (self.data or {}).get("status")
        if status == STATUS_CLEANING and self.water_tank:
            return STATUS_MOPPING
        return STATUS.get(status)

    def _current(self, prop: str, valid: dict[int, str], default: int) -> int:
        value = (self.data or {}).get(prop)
        return value if value in valid else default

    def resolve_rooms(self, rooms: list[str]) -> list[int]:
        """Room ids or configured names (case-insensitive) -> unique ids, in order."""
        by_name = {name.casefold(): rid for rid, name in self.rooms.items()}
        ids: list[int] = []
        for room in rooms:
            room = str(room).strip()
            rid = int(room) if room.isdigit() else by_name.get(room.casefold())
            if rid is None:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="unknown_room",
                    translation_placeholders={
                        "room": room,
                        "rooms": ", ".join(self.rooms.values()) or "-",
                    },
                )
            if rid not in ids:
                ids.append(rid)
        return ids
