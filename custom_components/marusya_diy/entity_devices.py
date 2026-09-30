"""Devices of an account: the YAML description plus entities picked in Home Assistant — by label or by list."""

# @tag:diy-sync
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import OPT_DEFAULT_ROOM, OPT_DEVICES, OPT_ENTITIES, OPT_LABEL
from .diy_yaml import Device, DevicesError, parse_devices

ON_OFF_TYPES = {
    "light": "light",
    "switch": "switch",
    "input_boolean": "switch",
    "automation": "switch",
    "fan": "other",
    "humidifier": "humidifier",
    "climate": "thermostat",
    "media_player": "media_device",
    "water_heater": "other",
    "remote": "other",
}
ONE_ACTION = {
    "script": "script/turn_on",
    "scene": "scene/turn_on",
    "button": "button/press",
    "input_button": "input_button/press",
    "vacuum": "vacuum/start",
}
PICKABLE_DOMAINS = sorted({*ON_OFF_TYPES, *ONE_ACTION})
_CLASS_TYPES = {
    ("switch", "outlet"): "socket",
    ("media_player", "tv"): "media_device.tv",
    ("media_player", "receiver"): "media_device.receiver",
}
_ONE_ACTION_TYPES = {"vacuum": "vacuum_cleaner"}


@dataclass(frozen=True)
class AccountDevices:
    devices: list[Device]
    skipped: list[str] = field(default_factory=list)


def account_devices(hass: HomeAssistant, options: Mapping[str, Any]) -> AccountDevices:
    """YAML devices go first and win over a picked entity they describe; unsupported labeled entities are skipped."""
    default_room = options.get(OPT_DEFAULT_ROOM, "")
    described = parse_devices(options.get(OPT_DEVICES, ""), default_room)
    entities = er.async_get(hass)
    picked = [e.entity_id for e in er.async_entries_for_label(entities, options[OPT_LABEL])] \
        if options.get(OPT_LABEL) else []
    picked = sorted(picked) + [e for e in options.get(OPT_ENTITIES, []) if e not in picked]
    skipped = [e for e in picked if e.split(".", 1)[0] not in PICKABLE_DOMAINS]
    described_entities = {d.entity_id for d in described}
    used_ids = {d.id for d in described}
    devices = list(described)
    unknown = []
    for entity_id in picked:
        if entity_id in described_entities or entity_id in skipped:
            continue
        device = _device_of(hass, entities, entity_id, default_room, used_ids)
        if device is None:
            unknown.append(entity_id)
            continue
        used_ids.add(device.id)
        devices.append(device)
    if unknown:
        raise DevicesError("unknown_entities", ", ".join(unknown))
    return AccountDevices(devices, skipped)


def _device_of(hass: HomeAssistant, entities: er.EntityRegistry, entity_id: str, default_room: str,
               used_ids: set[str]) -> Device | None:
    state = hass.states.get(entity_id)
    entry = entities.async_get(entity_id)
    if state is None and entry is None:
        return None
    domain, object_id = entity_id.split(".", 1)
    name = state.name if state is not None else (entry.name or entry.original_name or object_id)
    room = _area_name(hass, entry) or default_room
    if not room:
        raise DevicesError("no_room", entity_id)
    device_class = (state.attributes.get("device_class") if state is not None else None) or (
        entry and (entry.device_class or entry.original_device_class))
    service = ONE_ACTION.get(domain)
    device_type = (_ONE_ACTION_TYPES.get(domain, "other") if service
                   else _CLASS_TYPES.get((domain, device_class), ON_OFF_TYPES[domain]))
    device_id = object_id if object_id not in used_ids else f"{domain}_{object_id}"
    return Device(id=device_id, entity_id=entity_id, name=name, description=name, room=room,
                  type=device_type, service=service)


def _area_name(hass: HomeAssistant, entry: er.RegistryEntry | None) -> str:
    if entry is None:
        return ""
    area_id = entry.area_id
    if area_id is None and entry.device_id:
        device = dr.async_get(hass).async_get(entry.device_id)
        area_id = device.area_id if device else None
    area = ar.async_get(hass).async_get_area(area_id) if area_id else None
    return area.name if area else ""
