"""Marusya DIY: link Marusya speakers to Home Assistant through DIY Hooks without the mobile app."""

from __future__ import annotations

import logging

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import hook_token
from .api import MarusyaClient, MarusyaError
from .cabinet import Cabinet, CabinetError
from .const import CONF_CONFIG_ID, CONF_HOOK_USER_ID, CONF_SH_DATA, KIND, KIND_CABINET
from .runtime import (
    AccountRuntime, CabinetRuntime, account_entries, config_name, loaded_cabinet, new_cabinet_http, session_of,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if entry.data.get(KIND) == KIND_CABINET:
        http = new_cabinet_http(hass)
        entry.runtime_data = CabinetRuntime(Cabinet(http, entry.data[CONF_SH_DATA]), http)
        for account in account_entries(hass):
            account.runtime_data.schedule()
        return True

    runtime = AccountRuntime(hass, entry)
    entry.runtime_data = runtime
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_account_updated))
    runtime.schedule()
    return True


async def _async_account_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    runtime: AccountRuntime = entry.runtime_data
    if dict(entry.options) != runtime.options_seen:
        runtime.schedule()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if entry.data.get(KIND) == KIND_CABINET:
        entry.runtime_data.http.detach()
        return True
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Revoke the hook token; undo our own DIY link and configuration where the sessions still work."""
    if entry.data.get(KIND) == KIND_CABINET:
        return
    await hook_token.async_revoke(hass, entry.data.get(CONF_HOOK_USER_ID))
    if not entry.data.get(CONF_CONFIG_ID):
        return
    client = MarusyaClient(async_get_clientsession(hass), session_of(entry))
    try:
        if await client.diy_is_linked():
            await client.unlink_diy()
    except (MarusyaError, aiohttp.ClientError, TimeoutError) as err:
        _LOGGER.warning("%s: DIY stays linked at the Marusya server: %s", entry.title, err)
    cabinet = loaded_cabinet(hass)
    if cabinet is None:
        return
    try:
        for config in await cabinet.cabinet.configs():
            if config.name == config_name(entry):
                await cabinet.cabinet.remove(config.id)
    except (CabinetError, aiohttp.ClientError, TimeoutError) as err:
        _LOGGER.warning("%s: configuration %s stays in the DIY cabinet: %s", entry.title, config_name(entry), err)
