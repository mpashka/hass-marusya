import pytest
import yaml

from custom_components.marusya_diy.diy_yaml import DevicesError, fingerprint, parse_devices, render

DESCRIPTION = """
- entity_id: light.kitchen
  name: Свет
  type: light
- entity_id: script.cat_feed
  name: Корм кота
  type: other
  room: Гостиная
  id: feeder
  service: script/turn_on
"""


def test_defaults_and_hooks():
    devices = parse_devices(DESCRIPTION, "Кухня")
    config = yaml.safe_load(render(devices, "https://ha.example/", "TOKEN"))

    light, feeder = config
    assert (light["id"], light["room"], light["description"], light["type"]) == (
        "kitchen", "Кухня", "Свет", "devices.types.light")
    hooks = light["capabilities"][0]["hooks"]
    assert light["capabilities"][0]["retrievable"] is True
    assert hooks["on"]["url"] == "https://ha.example/api/services/light/turn_on"
    assert hooks["off"]["json"] == {"entity_id": "light.kitchen"}
    assert hooks["state"] == {"url": "https://ha.example/api/states/light.kitchen", "method": "GET",
                              "headers": {"Authorization": "Bearer TOKEN"}}
    assert (feeder["id"], feeder["room"]) == ("feeder", "Гостиная")
    assert feeder["capabilities"][0]["retrievable"] is False
    assert set(feeder["capabilities"][0]["hooks"]) == {"on"}
    assert feeder["capabilities"][0]["hooks"]["on"]["url"] == "https://ha.example/api/services/script/turn_on"


def test_fingerprint_follows_text():
    devices = parse_devices(DESCRIPTION, "Кухня")
    assert fingerprint(render(devices, "https://ha", "a")) != fingerprint(render(devices, "https://ha", "b"))
    assert fingerprint(render(devices, "https://ha", "a")) == fingerprint(render(devices, "https://ha", "a"))


def test_empty_description_is_no_devices():
    assert parse_devices("", "") == []


@pytest.mark.parametrize(("text", "reason"), [
    ("- [", "yaml_unreadable"),
    ("entity_id: light.a", "not_a_list"),
    ("- light.a", "device_not_a_mapping"),
    ("- {entity_id: light.a, name: A, type: light, colour: red}", "unknown_keys"),
    ("- {entity_id: Light A, name: A, type: light}", "bad_entity_id"),
    ("- {entity_id: light.a, type: light}", "no_name"),
    ("- {entity_id: light.a, name: A, type: lamp}", "bad_type"),
    ("- {entity_id: light.a, name: A, type: light, service: turn_on}", "bad_service"),
    ("- {entity_id: light.a, name: A, type: light, id: 'a b'}", "bad_id"),
    ("- {entity_id: light.a, name: A, type: light}\n- {entity_id: switch.a, name: B, type: switch}",
     "duplicate_ids"),
])
def test_refused_descriptions(text, reason):
    with pytest.raises(DevicesError) as err:
        parse_devices(text, "Кухня")
    assert err.value.reason == reason


def test_room_is_required_without_default():
    with pytest.raises(DevicesError) as err:
        parse_devices("- {entity_id: light.a, name: A, type: light}", "")
    assert err.value.reason == "no_room"
