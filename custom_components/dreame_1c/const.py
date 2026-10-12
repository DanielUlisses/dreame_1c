"""Constants for the Dreame 1C (dreame.vacuum.md1808) local integration."""
from __future__ import annotations

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "dreame_1c"
MODEL = "dreame.vacuum.md1808"

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.VACUUM,
]

CONF_ROOMS = "rooms"
CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 10  # seconds
REFRESH_AFTER_COMMAND = timedelta(seconds=2)

# Polled MIoT properties: name -> (siid, piid). See README for the spec link.
PROPS: dict[str, tuple[int, int]] = {
    "battery": (2, 1),
    "charging_state": (2, 2),
    "fault": (3, 1),
    "status": (3, 2),
    "work_mode": (18, 1),
    "cleaning_time": (18, 2),
    "cleaning_area": (18, 3),
    "fan_speed": (18, 6),
    "water_box": (18, 9),
    "total_clean_time": (18, 13),
    "total_clean_count": (18, 14),
    "total_clean_area": (18, 15),
    "water_level": (18, 20),
    "dnd": (20, 1),
    "dnd_start": (20, 2),
    "dnd_end": (20, 3),
    "warn_code": (22, 1),
    "volume": (24, 1),
    "main_brush_hours": (26, 1),
    "main_brush_life": (26, 2),
    "filter_life": (27, 1),
    "filter_hours": (27, 2),
    "side_brush_hours": (28, 1),
    "side_brush_life": (28, 2),
}
FIRMWARE = (1, 4)

# Actions: name -> (siid, aiid)
ACTION_RETURN_HOME = (2, 1)
ACTION_START_SWEEP = (3, 1)
ACTION_STOP_SWEEP = (3, 2)
ACTION_LOCATE = (17, 1)
ACTION_START_CLEAN = (18, 1)
ACTION_STOP_CLEAN = (18, 2)
ACTION_RESET_MAIN_BRUSH = (26, 1)
ACTION_RESET_FILTER = (27, 1)
ACTION_RESET_SIDE_BRUSH = (28, 1)

# 18.1 work-mode value used with action 18.1 + 18.21 (clean-info) for room cleaning.
# TODO: zone clean (work-mode 19) and spot clean (work-mode 20) are not implemented.
WORK_MODE_ROOM_CLEAN = 18
PIID_WORK_MODE = 1
PIID_CLEAN_INFO = 21

# 3.2 status
STATUS = {
    1: "cleaning",
    2: "idle",
    3: "paused",
    4: "error",
    5: "returning",
    6: "charging",
}
STATUS_CLEANING = 1
# Mopping is cleaning with the water tank fitted (18.9 = 1); it is not a robot status.
STATUS_MOPPING = "mopping"
CHARGING_STATES = (1, 4)  # 2.2 values that mean "on the dock, charging"

# 18.6 suction, 18.20 mop water level (value -> key)
FAN_SPEEDS = {0: "quiet", 1: "standard", 2: "medium", 3: "turbo"}
WATER_LEVELS = {1: "low", 2: "medium", 3: "high"}
FAN_BY_NAME = {name: value for value, name in FAN_SPEEDS.items()}
WATER_BY_NAME = {name: value for value, name in WATER_LEVELS.items()}
DEFAULT_FAN = 1
DEFAULT_WATER = 2

# 22.1 warn-code
WARN_CODES = {
    0: "normal",
    1: "drop",
    2: "cliff",
    3: "bumper",
    4: "gesture",
    5: "bumper_repeat",
    6: "drop_repeat",
    7: "optical_flow",
    8: "no_box",
    9: "no_tankbox",
    10: "waterbox_empty",
    11: "box_full",
    12: "brush",
    13: "side_brush",
    14: "fan",
    15: "left_wheel_motor",
    16: "right_wheel_motor",
    17: "turn_suffocate",
    18: "forward_suffocate",
    19: "charger_get",
    20: "battery_low",
    21: "charge_fault",
    22: "battery_percentage",
    23: "heart",
    24: "camera_occlusion",
    25: "camera_fault",
    26: "event_battery",
    27: "forward_looking",
    28: "gyroscope",
}

SERVICE_CLEAN_ROOMS = "clean_rooms"
ATTR_ROOMS = "rooms"
ATTR_FAN_SPEED = "fan_speed"
ATTR_WATER_LEVEL = "water_level"
ATTR_REPEATS = "repeats"


def parse_rooms(text: str | None) -> dict[int, str]:
    """Parse '1=Suite, 2=Escritorio' (commas or newlines) into {1: 'Suite', ...}.

    Raises ValueError on malformed input.
    """
    rooms: dict[int, str] = {}
    for part in (text or "").replace("\n", ",").split(","):
        if not part.strip():
            continue
        room_id, sep, name = part.partition("=")
        if not sep or not name.strip():
            raise ValueError(f"invalid room entry: {part.strip()!r}")
        rooms[int(room_id.strip())] = name.strip()
    return rooms
