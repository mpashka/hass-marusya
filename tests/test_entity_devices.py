import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import label_registry as lr

from custom_components.marusya_diy.const import OPT_DEFAULT_ROOM, OPT_DEVICES, OPT_ENTITIES, OPT_LABEL
from custom_components.marusya_diy.diy_yaml import DevicesError
from custom_components.marusya_diy.entity_devices import account_devices


def registered(hass: HomeAssistant, entity_id: str, name: str, **attributes) -> er.RegistryEntry:
    domain, object_id = entity_id.split(".", 1)
    entry = er.async_get(hass).async_get_or_create(domain, "test", object_id, suggested_object_id=object_id)
    hass.states.async_set(entity_id, "off", {"friendly_name": name, **attributes})
    return entry


async def test_picked_entity_takes_name_type_and_area(hass):
    registered(hass, "switch.kettle_plug", "Чайник", device_class="outlet")
    area = ar.async_get(hass).async_create("Кухня")
    er.async_get(hass).async_update_entity("switch.kettle_plug", area_id=area.id)
    registered(hass, "script.cat_feed", "Корм кота")

    picked = account_devices(hass, {OPT_ENTITIES: ["switch.kettle_plug", "script.cat_feed"],
                                    OPT_DEFAULT_ROOM: "Дом"})

    plug, script = picked.devices
    assert (plug.name, plug.type, plug.room, plug.service) == ("Чайник", "socket", "Кухня", None)
    assert (script.type, script.room, script.service) == ("other", "Дом", "script/turn_on")


async def test_label_brings_entities_and_skips_unsupported(hass):
    label = lr.async_get(hass).async_create("Маруся: кухня")
    for entity_id in ("light.kitchen", "sensor.kitchen_temperature"):
        registered(hass, entity_id, entity_id)
        er.async_get(hass).async_update_entity(entity_id, labels={label.label_id})

    picked = account_devices(hass, {OPT_LABEL: label.label_id, OPT_DEFAULT_ROOM: "Кухня"})

    assert [d.entity_id for d in picked.devices] == ["light.kitchen"]
    assert picked.skipped == ["sensor.kitchen_temperature"]


async def test_yaml_wins_over_picked_and_ids_stay_unique(hass):
    registered(hass, "light.kitchen", "Люстра")
    registered(hass, "switch.kitchen", "Розетка")
    yaml_text = "- {entity_id: light.kitchen, name: Свет, type: light}\n"

    picked = account_devices(hass, {OPT_DEVICES: yaml_text, OPT_ENTITIES: ["light.kitchen", "switch.kitchen"],
                                    OPT_DEFAULT_ROOM: "Кухня"})

    assert [(d.id, d.name) for d in picked.devices] == [("kitchen", "Свет"), ("switch_kitchen", "Розетка")]


async def test_picked_entity_without_room_is_refused(hass):
    registered(hass, "light.hall", "Свет")
    with pytest.raises(DevicesError) as err:
        account_devices(hass, {OPT_ENTITIES: ["light.hall"]})
    assert (err.value.reason, err.value.where) == ("no_room", "light.hall")
