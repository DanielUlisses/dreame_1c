"""Sensors for the Dreame 1C."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfArea, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import STATUS, STATUS_MOPPING, WARN_CODES
from .coordinator import Dreame1CConfigEntry, Dreame1CCoordinator
from .entity import Dreame1CEntity

PARALLEL_UPDATES = 0  # the coordinator serialises robot access


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True, kw_only=True)
class Dreame1CSensorDescription(SensorEntityDescription):
    prop: str
    convert: Callable[[Any], Any] = lambda v: v
    # Derived values that need more than one prop; overrides prop/convert.
    value_fn: Callable[[Dreame1CCoordinator], Any] | None = None


def _life(key: str, prop: str) -> Dreame1CSensorDescription:
    return Dreame1CSensorDescription(
        key=key,
        translation_key=key,
        prop=prop,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    )


def _hours_left(key: str, prop: str) -> Dreame1CSensorDescription:
    return Dreame1CSensorDescription(
        key=key,
        translation_key=key,
        prop=prop,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    )


SENSORS: tuple[Dreame1CSensorDescription, ...] = (
    Dreame1CSensorDescription(
        key="status",
        translation_key="status",
        prop="status",
        device_class=SensorDeviceClass.ENUM,
        options=[*STATUS.values(), STATUS_MOPPING],
        value_fn=lambda coordinator: coordinator.status,
    ),
    Dreame1CSensorDescription(
        key="warn_code",
        translation_key="warn_code",
        prop="warn_code",
        device_class=SensorDeviceClass.ENUM,
        options=list(WARN_CODES.values()),
        convert=WARN_CODES.get,
    ),
    Dreame1CSensorDescription(
        key="fault",
        translation_key="fault",
        prop="fault",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    Dreame1CSensorDescription(
        key="work_mode",
        translation_key="work_mode",
        prop="work_mode",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    Dreame1CSensorDescription(
        key="battery",
        prop="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Dreame1CSensorDescription(
        key="cleaning_area",
        translation_key="cleaning_area",
        prop="cleaning_area",
        device_class=SensorDeviceClass.AREA,
        native_unit_of_measurement=UnitOfArea.SQUARE_METERS,
        state_class=SensorStateClass.MEASUREMENT,
        convert=_float,
    ),
    Dreame1CSensorDescription(
        key="cleaning_time",
        translation_key="cleaning_time",
        prop="cleaning_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    Dreame1CSensorDescription(
        key="total_clean_time",
        translation_key="total_clean_time",
        prop="total_clean_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    Dreame1CSensorDescription(
        key="total_clean_count",
        translation_key="total_clean_count",
        prop="total_clean_count",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    Dreame1CSensorDescription(
        key="total_clean_area",
        translation_key="total_clean_area",
        prop="total_clean_area",
        device_class=SensorDeviceClass.AREA,
        native_unit_of_measurement=UnitOfArea.SQUARE_METERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    _life("filter_life", "filter_life"),
    _hours_left("filter_hours", "filter_hours"),
    _life("main_brush_life", "main_brush_life"),
    _hours_left("main_brush_hours", "main_brush_hours"),
    _life("side_brush_life", "side_brush_life"),
    _hours_left("side_brush_hours", "side_brush_hours"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Dreame1CConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(Dreame1CSensor(entry.runtime_data, d) for d in SENSORS)


class Dreame1CSensor(Dreame1CEntity, SensorEntity):
    entity_description: Dreame1CSensorDescription

    def __init__(
        self, coordinator: Dreame1CCoordinator, description: Dreame1CSensorDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        if self.entity_description.value_fn:
            return self.entity_description.value_fn(self.coordinator)
        value = self._value(self.entity_description.prop)
        return None if value is None else self.entity_description.convert(value)
