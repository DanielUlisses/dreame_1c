"""Thin blocking client over python-miio for the Dreame 1C (MIoT over local miio).

Every method blocks on UDP I/O: call them through hass.async_add_executor_job.
"""
from __future__ import annotations

import json
import threading
from typing import Any

from miio import Device, DeviceException

from .const import ACTION_START_CLEAN, PIID_CLEAN_INFO, PIID_WORK_MODE, WORK_MODE_ROOM_CLEAN

CHUNK = 8  # the robot rejects larger get_properties batches


class DreameError(Exception):
    """Raised when the robot is unreachable or rejects a command."""


class DreameClient:
    """Blocking MIoT client; serialises access since miio sockets are not thread-safe."""

    def __init__(self, host: str, token: str) -> None:
        self._device = Device(host, token, timeout=5)
        self._lock = threading.Lock()

    def _send(self, method: str, params: Any) -> Any:
        with self._lock:
            try:
                return self._device.send(method, params)
            except DeviceException as err:
                raise DreameError(f"{method} failed: {err}") from err

    @property
    def device_id(self) -> int:
        """miio device id (valid after the first successful call)."""
        return self._device.device_id

    def get_props(self, props: dict[str, tuple[int, int]]) -> dict[str, Any]:
        """Read props {name: (siid, piid)} -> {name: value}; unreadable ones are None."""
        by_key = {v: k for k, v in props.items()}
        keys = list(props.values())
        out: dict[str, Any] = dict.fromkeys(props)
        for i in range(0, len(keys), CHUNK):
            req = [{"did": "0", "siid": s, "piid": p} for s, p in keys[i : i + CHUNK]]
            for res in self._send("get_properties", req) or []:
                name = by_key.get((res.get("siid"), res.get("piid")))
                if name is not None and res.get("code", 0) == 0:
                    out[name] = res.get("value")
        return out

    def set_prop(self, siid: int, piid: int, value: Any) -> None:
        res = self._send(
            "set_properties", [{"did": "0", "siid": siid, "piid": piid, "value": value}]
        )
        _check([r.get("code", 0) for r in res or []], f"set {siid}.{piid}")

    def action(self, siid: int, aiid: int, args: list[dict[str, Any]] | None = None) -> None:
        res = self._send(
            "action", {"did": "0", "siid": siid, "aiid": aiid, "in": args or []}
        )
        code = res.get("code", 0) if isinstance(res, dict) else 0
        _check([code], f"action {siid}.{aiid}")

    def clean_rooms(self, rooms: list[int], repeats: int, fan: int, water: int) -> None:
        """Room clean: action 18.1 with work-mode 18 and clean-info selects."""
        selects = [[room, repeats, fan, water, 1] for room in rooms]
        self.action(
            *ACTION_START_CLEAN,
            [
                {"piid": PIID_WORK_MODE, "value": WORK_MODE_ROOM_CLEAN},
                {"piid": PIID_CLEAN_INFO, "value": json.dumps({"selects": selects})},
            ],
        )


def _check(codes: list[int], what: str) -> None:
    if any(code != 0 for code in codes):
        raise DreameError(f"{what} rejected by robot (codes {codes})")
