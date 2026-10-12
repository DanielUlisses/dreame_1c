import json
from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from custom_components.dreame_1c.api import DreameClient, DreameError

TOKEN = "0123456789abcdef0123456789ABCDEF"

STATE = {
    (2, 1): 87, (2, 2): 1, (3, 1): 0, (3, 2): 6, (18, 1): 6, (18, 2): 12, (18, 3): "15",
    (18, 6): 2, (18, 9): 0, (18, 13): 1234, (18, 14): 50, (18, 15): 800, (18, 20): 3,
    (18, 22): 0, (20, 1): False, (20, 2): "22:00", (20, 3): "08:00", (22, 1): 0, (24, 1): 70,
    (26, 1): 200, (26, 2): 66, (27, 1): 40, (27, 2): 60, (28, 1): 100, (28, 2): 50, (1, 4): "3.5.8_1096",
}


class FakeDevice:
    """Stands in for miio.Device: records sends and answers like the robot."""

    sent: list = []
    device_id = 123456789

    def __init__(self, *a, **kw):
        pass

    def send(self, method, params):
        FakeDevice.sent.append((method, params))
        if method == "get_properties":
            assert len(params) <= 8
            out = []
            for p in params:
                key = (p["siid"], p["piid"])
                if key in STATE:
                    out.append({**p, "code": 0, "value": STATE[key]})
                else:
                    out.append({**p, "code": -1})
            return out
        if method == "set_properties":
            for p in params:
                STATE[(p["siid"], p["piid"])] = p["value"]
            return [{**p, "code": 0} for p in params]
        if method == "action":
            return {"code": 0}
        raise AssertionError(method)


@pytest.fixture(autouse=True)
def fake_device():
    FakeDevice.sent = []
    with patch("custom_components.dreame_1c.api.Device", FakeDevice):
        yield FakeDevice


async def _setup(hass: HomeAssistant, rooms="1=Suite, 2=Escritorio"):
    r = await hass.config_entries.flow.async_init("dreame_1c", context={"source": config_entries.SOURCE_USER})
    assert r["type"] is FlowResultType.FORM
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"host": "10.0.0.5", "token": "bad"})
    assert r["errors"] == {"token": "invalid_token"}
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"host": " 10.0.0.5 ", "token": TOKEN})
    assert r["type"] is FlowResultType.CREATE_ENTRY, r
    entry = r["result"]
    assert entry.unique_id == "123456789"
    assert entry.data == {"host": "10.0.0.5", "token": TOKEN.lower()}
    await hass.async_block_till_done()

    r = await hass.config_entries.options.async_init(entry.entry_id)
    r = await hass.config_entries.options.async_configure(r["flow_id"], {"rooms": "nope", "scan_interval": 10})
    assert r["errors"] == {"rooms": "invalid_rooms"}
    r = await hass.config_entries.options.async_configure(r["flow_id"], {"rooms": rooms, "scan_interval": 15})
    assert r["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    return entry


async def test_full(hass: HomeAssistant, fake_device):
    entry = await _setup(hass)
    assert entry.state is config_entries.ConfigEntryState.LOADED
    states = {s.entity_id: s for s in hass.states.async_all()}
    for eid, s in sorted(states.items()):
        print(eid, s.state, s.attributes.get("friendly_name"))

    vac = hass.states.get("vacuum.dreame_1c")
    assert vac.state == "docked"
    assert vac.attributes["fan_speed"] == "medium"
    assert hass.states.get("sensor.dreame_1c_status").state == "charging"
    assert hass.states.get("sensor.dreame_1c_battery").state == "87"
    assert hass.states.get("sensor.dreame_1c_cleaning_area").state == "15.0"
    assert hass.states.get("select.dreame_1c_mop_water_level").state == "high"
    assert hass.states.get("switch.dreame_1c_do_not_disturb").state == "off"
    assert hass.states.get("number.dreame_1c_volume").state == "70"
    assert hass.states.get("button.dreame_1c_clean_suite")
    assert hass.states.get("button.dreame_1c_clean_escritorio")

    fake_device.sent.clear()
    await hass.services.async_call("button", "press", {"entity_id": "button.dreame_1c_clean_suite"}, blocking=True)
    (method, params), = fake_device.sent
    assert method == "action" and params["siid"] == 18 and params["aiid"] == 1
    assert params["in"][0] == {"piid": 1, "value": 18}
    assert json.loads(params["in"][1]["value"]) == {"selects": [[1, 1, 2, 3, 1]]}

    fake_device.sent.clear()
    await hass.services.async_call(
        "dreame_1c", "clean_rooms",
        {"entity_id": "vacuum.dreame_1c", "rooms": ["escritorio", "1", "7"], "fan_speed": "turbo", "water_level": "low", "repeats": 2},
        blocking=True,
    )
    (method, params), = fake_device.sent
    assert json.loads(params["in"][1]["value"]) == {"selects": [[2, 2, 3, 1, 1], [1, 2, 3, 1, 1], [7, 2, 3, 1, 1]]}

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call("dreame_1c", "clean_rooms", {"entity_id": "vacuum.dreame_1c", "rooms": ["Cozinha"]}, blocking=True)

    for svc, expect in [("start", (3, 1)), ("pause", (3, 2)), ("stop", (18, 2)), ("return_to_base", (2, 1)), ("locate", (17, 1))]:
        fake_device.sent.clear()
        await hass.services.async_call("vacuum", svc, {"entity_id": "vacuum.dreame_1c"}, blocking=True)
        (method, params), = fake_device.sent
        assert (method, params["siid"], params["aiid"]) == ("action", *expect), svc

    fake_device.sent.clear()
    await hass.services.async_call("vacuum", "set_fan_speed", {"entity_id": "vacuum.dreame_1c", "fan_speed": "quiet"}, blocking=True)
    assert fake_device.sent[0] == ("set_properties", [{"did": "0", "siid": 18, "piid": 6, "value": 0}])
    assert hass.states.get("vacuum.dreame_1c").attributes["fan_speed"] == "quiet"

    await hass.services.async_call("select", "select_option", {"entity_id": "select.dreame_1c_mop_water_level", "option": "low"}, blocking=True)
    await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.dreame_1c_do_not_disturb"}, blocking=True)
    await hass.services.async_call("number", "set_value", {"entity_id": "number.dreame_1c_volume", "value": 30}, blocking=True)
    assert STATE[(18, 20)] == 1 and STATE[(20, 1)] is True and STATE[(24, 1)] == 30
    await hass.services.async_call("button", "press", {"entity_id": "button.dreame_1c_reset_filter"}, blocking=True)

    # robot rejects -> HomeAssistantError
    with patch.object(FakeDevice, "send", return_value={"code": -4004}):
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call("vacuum", "locate", {"entity_id": "vacuum.dreame_1c"}, blocking=True)

    # removing a room drops its button
    hass.config_entries.async_update_entry(entry, options={**entry.options, "rooms": "1=Suite"})
    await hass.async_block_till_done()
    reg = er.async_get(hass)
    assert reg.async_get("button.dreame_1c_clean_escritorio") is None
    assert reg.async_get("button.dreame_1c_clean_suite") is not None

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_cannot_connect(hass: HomeAssistant):
    with patch.object(FakeDevice, "send", side_effect=__import__("miio").DeviceException("timeout")):
        r = await hass.config_entries.flow.async_init("dreame_1c", context={"source": config_entries.SOURCE_USER})
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"host": "10.0.0.5", "token": TOKEN})
    assert r["errors"] == {"base": "cannot_connect"}


async def test_returning_state(hass: HomeAssistant):
    STATE[(3, 2)] = 5
    try:
        await _setup(hass)
        assert hass.states.get("vacuum.dreame_1c").state == "returning"
    finally:
        STATE[(3, 2)] = 6


async def test_service_description_and_ptbr(hass: HomeAssistant):
    from homeassistant.helpers.service import async_get_all_descriptions
    from homeassistant.helpers.translation import async_get_translations
    await _setup(hass)
    desc = await async_get_all_descriptions(hass)
    print(desc["dreame_1c"]["clean_rooms"])
    assert set(desc["dreame_1c"]["clean_rooms"]["fields"]) == {"rooms", "fan_speed", "water_level", "repeats"}
    tr = await async_get_translations(hass, "pt-BR", "entity", ["dreame_1c"])
    assert tr["component.dreame_1c.entity.button.clean_room.name"] == "Limpar {room}"
    tr = await async_get_translations(hass, "pt-BR", "services", ["dreame_1c"])
    assert tr["component.dreame_1c.services.clean_rooms.name"] == "Limpar cômodos"


async def test_reconfigure_same_and_other_robot(hass: HomeAssistant, fake_device):
    entry = await _setup(hass)

    r = await hass.config_entries.flow.async_init("dreame_1c", context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id})
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {"host": "10.0.0.9", "token": TOKEN})
    assert r["type"] is FlowResultType.ABORT and r["reason"] == "reconfigure_successful"
    assert entry.data["host"] == "10.0.0.9"
    await hass.async_block_till_done()

    with patch.object(FakeDevice, "device_id", 999):
        r = await hass.config_entries.flow.async_init("dreame_1c", context={"source": config_entries.SOURCE_RECONFIGURE, "entry_id": entry.entry_id})
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"host": "10.0.0.7", "token": TOKEN})
    assert r["type"] is FlowResultType.ABORT and r["reason"] == "wrong_device"
    assert entry.data["host"] == "10.0.0.9"


async def test_mopping_vs_vacuuming(hass: HomeAssistant, fake_device):
    STATE[(3, 2)], STATE[(18, 9)] = 1, 1  # cleaning, water tank fitted
    try:
        await _setup(hass)
        assert hass.states.get("binary_sensor.dreame_1c_water_tank").state == "on"
        assert hass.states.get("sensor.dreame_1c_status").state == "mopping"
        vac = hass.states.get("vacuum.dreame_1c")
        assert vac.state == "cleaning"
        assert vac.attributes["status"] == "Mopping"
        assert vac.attributes["cleaning_mode"] == "mopping"

        STATE[(18, 9)] = 0  # tank removed: plain vacuuming
        coordinator = hass.config_entries.async_entries("dreame_1c")[0].runtime_data
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert hass.states.get("binary_sensor.dreame_1c_water_tank").state == "off"
        assert hass.states.get("sensor.dreame_1c_status").state == "cleaning"
        vac = hass.states.get("vacuum.dreame_1c")
        assert vac.attributes["status"] == "cleaning"
        assert vac.attributes["cleaning_mode"] == "vacuuming"
    finally:
        STATE[(3, 2)], STATE[(18, 9)] = 6, 0


async def test_cleaning_rooms_attribute(hass: HomeAssistant, fake_device):
    entry = await _setup(hass)
    coordinator = entry.runtime_data
    await hass.services.async_call(
        "dreame_1c", "clean_rooms", {"entity_id": "vacuum.dreame_1c", "rooms": ["suite", "2"]}, blocking=True
    )
    STATE[(18, 1)] = 18  # robot switched to room cleaning
    try:
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert hass.states.get("vacuum.dreame_1c").attributes["cleaning_rooms"] == "Suite, Escritorio"

        STATE[(18, 1)] = 6  # back on the dock
        with patch("custom_components.dreame_1c.coordinator.ROOMS_GRACE", 0):
            await coordinator.async_refresh()
            await hass.async_block_till_done()
        assert hass.states.get("vacuum.dreame_1c").attributes["cleaning_rooms"] is None
    finally:
        STATE[(18, 1)] = 6


async def test_clean_area_segments(hass: HomeAssistant, fake_device):
    await _setup(hass)
    registry = er.async_get(hass)
    entity = hass.data["entity_components"]["vacuum"].get_entity("vacuum.dreame_1c")
    assert [(s.id, s.name) for s in await entity.async_get_segments()] == [("1", "Suite"), ("2", "Escritorio")]

    # The user maps segments to HA areas in the vacuum's settings.
    registry.async_update_entity_options(
        "vacuum.dreame_1c", "vacuum",
        {"area_mapping": {"suite_area": ["1"], "office_area": ["2"]},
         "last_seen_segments": [{"id": "1", "name": "Suite", "group": None},
                                {"id": "2", "name": "Escritorio", "group": None}]},
    )
    fake_device.sent.clear()
    await hass.services.async_call(
        "vacuum", "clean_area",
        {"entity_id": "vacuum.dreame_1c", "cleaning_area_id": ["office_area", "suite_area"]},
        blocking=True,
    )
    (method, params), = fake_device.sent
    assert method == "action" and (params["siid"], params["aiid"]) == (18, 1)
    selects = json.loads(params["in"][1]["value"])["selects"]
    assert [s[0] for s in selects] == [2, 1]
