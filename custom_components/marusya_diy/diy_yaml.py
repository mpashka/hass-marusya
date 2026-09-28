"""Device description of an account → DIY configuration text with hooks to Home Assistant."""

# @tag:diy-sync
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

import yaml

DEVICE_TYPES = frozenset({
    "light", "socket", "switch", "thermostat", "thermostat.ac",
    "media_device", "media_device.tv", "media_device.tv_box", "media_device.receiver",
    "cooking", "cooking.coffee_maker", "cooking.kettle", "cooking.multicooker",
    "openable", "openable.curtain", "humidifier", "purifier", "vacuum_cleaner",
    "washing_machine", "dishwasher", "iron", "sensor", "other",
})
_ENTITY_ID = re.compile(r"^[a-z0-9_]+\.[a-z0-9_]+$")
_SERVICE = re.compile(r"^[a-z0-9_]+/[a-z0-9_]+$")
_DEVICE_ID = re.compile(r"^[A-Za-z0-9_\-]+$")
_KEYS = frozenset({"id", "entity_id", "name", "description", "room", "type", "service"})


class DevicesError(ValueError):
    """The description is wrong; `reason` is a translation key, `where` names the device."""

    def __init__(self, reason: str, where: str = "") -> None:
        super().__init__(f"{reason}: {where}" if where else reason)
        self.reason = reason
        self.where = where


@dataclass(frozen=True)
class Device:
    id: str
    entity_id: str
    name: str
    description: str
    room: str
    type: str
    service: str | None = None


def parse_devices(text: str, default_room: str) -> list[Device]:
    try:
        items = yaml.safe_load(text or "") or []
    except yaml.YAMLError as err:
        raise DevicesError("yaml_unreadable", str(err).splitlines()[0]) from err
    if not isinstance(items, list):
        raise DevicesError("not_a_list")
    devices: list[Device] = []
    for number, item in enumerate(items, 1):
        where = f"#{number}"
        if not isinstance(item, dict):
            raise DevicesError("device_not_a_mapping", where)
        where = f"#{number} {item.get('entity_id', '')}".strip()
        unknown = set(item) - _KEYS
        if unknown:
            raise DevicesError("unknown_keys", f"{where}: {', '.join(sorted(map(str, unknown)))}")
        entity_id = str(item.get("entity_id") or "")
        if not _ENTITY_ID.match(entity_id):
            raise DevicesError("bad_entity_id", where)
        name = str(item.get("name") or "").strip()
        if not name:
            raise DevicesError("no_name", where)
        device_type = str(item.get("type") or "")
        if device_type not in DEVICE_TYPES:
            raise DevicesError("bad_type", f"{where}: {device_type}")
        room = str(item.get("room") or default_room or "").strip()
        if not room:
            raise DevicesError("no_room", where)
        service = item.get("service")
        if service is not None and not _SERVICE.match(str(service)):
            raise DevicesError("bad_service", where)
        device_id = str(item.get("id") or entity_id.split(".", 1)[1])
        if not _DEVICE_ID.match(device_id):
            raise DevicesError("bad_id", where)
        devices.append(Device(
            id=device_id, entity_id=entity_id, name=name,
            description=str(item.get("description") or name), room=room, type=device_type,
            service=str(service) if service is not None else None,
        ))
    ids = [d.id for d in devices]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise DevicesError("duplicate_ids", ", ".join(duplicates))
    return devices


def render(devices: list[Device], base_url: str, token: str) -> str:
    base_url = base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def call(service: str, entity_id: str) -> dict:
        return {"url": f"{base_url}/api/services/{service}", "method": "POST",
                "json": {"entity_id": entity_id}, "headers": headers}

    config = []
    for device in devices:
        if device.service:
            hooks = {"on": call(device.service, device.entity_id)}
        else:
            domain = device.entity_id.split(".", 1)[0]
            hooks = {
                "on": call(f"{domain}/turn_on", device.entity_id),
                "off": call(f"{domain}/turn_off", device.entity_id),
                "state": {"url": f"{base_url}/api/states/{device.entity_id}", "method": "GET",
                          "headers": {"Authorization": f"Bearer {token}"}},
            }
        config.append({
            "id": device.id,
            "name": device.name,
            "description": device.description,
            "room": device.room,
            "type": f"devices.types.{device.type}",
            "custom_data": None,
            "capabilities": [{
                "type": "devices.capabilities.on_off",
                "retrievable": device.service is None,
                "parameters": None,
                "hooks": hooks,
            }],
        })
    return yaml.safe_dump(config, allow_unicode=True, sort_keys=False)


def fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()
