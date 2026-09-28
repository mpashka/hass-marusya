"""«DIY state» entity of an account: what sync achieved or why it stopped."""

# @tag:diy-sync
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .runtime import STATES, AccountRuntime


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([DiyStateSensor(entry)])


class DiyStateSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "diy_state"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = STATES
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry) -> None:
        self._runtime: AccountRuntime = entry.runtime_data
        self._attr_unique_id = f"{entry.entry_id}_diy_state"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)}, name=entry.title,
                                            manufacturer="VK", model="Marusya account")

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._runtime.add_listener(self.async_write_ha_state))

    @property
    def native_value(self) -> str:
        return self._runtime.status.state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        status = self._runtime.status
        return {
            "detail": status.detail,
            "configuration": status.config_name,
            "devices": status.devices,
            "missing": status.missing,
            "finished": status.finished.isoformat() if status.finished else None,
        }
