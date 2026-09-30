"""Runtime of loaded entries: the cabinet session and the sync state of every account."""

# @tag:diy-sync
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

import aiohttp
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_create_clientsession, async_get_clientsession
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.start import async_at_started
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify

from . import hook_token
from .api import MarusyaClient, MarusyaError, MarusyaSessionGone, Session
from .cabinet import Cabinet, CabinetError, CabinetSessionGone
from .const import (
    CONF_ACCOUNT_ID, CONF_CONFIG_FINGERPRINT, CONF_CONFIG_ID, CONF_CONFIG_NAME, CONF_DEVICE_ID,
    CONF_HOOK_REFRESH_TOKEN_ID, CONF_HOOK_TOKEN, CONF_HOOK_USER_ID, CONF_SESSION_ID, CONF_SESSION_SECRET,
    CONF_VK_USER_ID, DOMAIN, KIND, KIND_ACCOUNT, KIND_CABINET, OPT_BASE_URL, OPT_ENTITIES, OPT_LABEL,
)
from .diy_yaml import Device, DevicesError, render
from .entity_devices import account_devices
from .sync import STATE_LINKED, STATE_NO_DEVICES, STATE_UNCHANGED, Linked, SyncError, async_sync

_LOGGER = logging.getLogger(__name__)

STATE_SYNCING = "syncing"
STATE_WAITING_CABINET = "waiting_cabinet"
STATE_REAUTH = "reauth"
STATE_ERROR = "error"
STATES = [STATE_SYNCING, STATE_LINKED, STATE_NO_DEVICES, STATE_WAITING_CABINET, STATE_REAUTH, STATE_ERROR]


@dataclass
class CabinetRuntime:
    cabinet: Cabinet
    http: aiohttp.ClientSession


@dataclass
class Status:
    state: str = STATE_SYNCING
    detail: str = ""
    config_name: str = ""
    devices: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    finished: datetime | None = None


def new_cabinet_http(hass: HomeAssistant) -> aiohttp.ClientSession:
    """Own cookie jar: the cabinet keeps its session and CSRF token in cookies."""
    return async_create_clientsession(hass, auto_cleanup=False, cookie_jar=aiohttp.CookieJar())


def config_name(entry: ConfigEntry) -> str:
    return f"hass-{slugify(entry.title) or entry.entry_id}.yaml"


def session_of(entry: ConfigEntry) -> Session:
    data = entry.data
    return Session(data[CONF_DEVICE_ID], data[CONF_SESSION_ID], data[CONF_SESSION_SECRET],
                   data[CONF_ACCOUNT_ID], data[CONF_VK_USER_ID])


def loaded_cabinet(hass: HomeAssistant) -> CabinetRuntime | None:
    """The cabinet entry schedules account syncs from its own setup, before it is marked loaded."""
    entry = cabinet_entry(hass)
    if entry is None or entry.state not in (ConfigEntryState.LOADED, ConfigEntryState.SETUP_IN_PROGRESS):
        return None
    runtime = getattr(entry, "runtime_data", None)
    return runtime if isinstance(runtime, CabinetRuntime) else None


def cabinet_entry(hass: HomeAssistant) -> ConfigEntry | None:
    return next((e for e in hass.config_entries.async_entries(DOMAIN) if e.data.get(KIND) == KIND_CABINET), None)


class AccountRuntime:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._hass = hass
        self._entry = entry
        self._lock = asyncio.Lock()
        self._listeners: list[Callable[[], None]] = []
        self.status = Status()
        self.options_seen = dict(entry.options)
        self._built: list[Device] | None = None
        self._started = asyncio.Event()
        entry.async_on_unload(async_at_started(hass, self._on_started))
        for event_type in (er.EVENT_ENTITY_REGISTRY_UPDATED, dr.EVENT_DEVICE_REGISTRY_UPDATED,
                           ar.EVENT_AREA_REGISTRY_UPDATED):
            entry.async_on_unload(hass.bus.async_listen(event_type, self._on_registry_updated))

    async def _on_started(self, hass: HomeAssistant) -> None:
        self._started.set()

    @callback
    def _on_registry_updated(self, event: Event) -> None:
        """Picked devices follow names, areas and labels; the cloud is asked only when the list really changed."""
        options = self._entry.options
        if not (options.get(OPT_LABEL) or options.get(OPT_ENTITIES)) or self._built is None:
            return
        try:
            devices = account_devices(self._hass, options).devices
        except DevicesError:
            return
        if devices != self._built:
            self.schedule()

    @callback
    def add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    @callback
    def schedule(self, force: bool = False) -> None:
        self._entry.async_create_background_task(self._hass, self.async_run(force), f"{DOMAIN} sync")

    async def async_run(self, force: bool = False) -> None:
        await self._started.wait()
        async with self._lock:
            self._set(Status(STATE_SYNCING, config_name=self.status.config_name))
            self.options_seen = dict(self._entry.options)
            try:
                self._set(await self._sync(force))
            except MarusyaSessionGone as err:
                self._set(Status(STATE_REAUTH, f"{err.step}: {err.detail}"))
                self._entry.async_start_reauth(self._hass)
            except CabinetSessionGone as err:
                self._set(Status(STATE_WAITING_CABINET, f"{err.step}: {err.detail}"))
                if (entry := cabinet_entry(self._hass)) is not None:
                    entry.async_start_reauth(self._hass)
            except SyncError as err:
                rollback = "previous configuration relinked" if err.rolled_back else "account may be left without DIY"
                self._set(Status(STATE_ERROR, f"{err.step}: {err.detail}; {rollback}"))
            except (MarusyaError, CabinetError) as err:
                self._set(Status(STATE_ERROR, f"{err.step}: {err.detail}"))
            except (aiohttp.ClientError, TimeoutError) as err:
                self._set(Status(STATE_ERROR, f"network: {type(err).__name__} {err}"))

    async def _sync(self, force: bool) -> Status:
        cabinet = loaded_cabinet(self._hass)
        if cabinet is None:
            return Status(STATE_WAITING_CABINET, "no DIY cabinet session: add the «DIY cabinet session» entry")
        try:
            picked = account_devices(self._hass, self._entry.options)
        except DevicesError as err:
            self._built = []
            return Status(STATE_ERROR, f"device description: {err}")
        devices = self._built = picked.devices
        text = ""
        if devices:
            try:
                base_url = self._entry.options.get(OPT_BASE_URL) or get_url(
                    self._hass, allow_internal=False, allow_ip=False, require_ssl=True)
            except NoURLAvailableError:
                return Status(STATE_ERROR, "Home Assistant has no external https address: set it in "
                                           "Settings → System → Network or in the entry options (base_url)")
            text = render(devices, base_url, await self._hook_token())
        data = self._entry.data
        previous = (Linked(data[CONF_CONFIG_ID], data[CONF_CONFIG_NAME], data[CONF_CONFIG_FINGERPRINT])
                    if data.get(CONF_CONFIG_ID) else None)
        client = MarusyaClient(async_get_clientsession(self._hass), session_of(self._entry))
        outcome = await async_sync(client, cabinet.cabinet, config_name(self._entry), text,
                                   [d.id for d in devices], previous, force)
        linked = outcome.linked
        if linked != previous:
            self._update_data({CONF_CONFIG_ID: linked.config_id if linked else None,
                               CONF_CONFIG_NAME: linked.config_name if linked else None,
                               CONF_CONFIG_FINGERPRINT: linked.fingerprint if linked else None})
        state = STATE_LINKED if outcome.state == STATE_UNCHANGED else outcome.state
        devices_seen = [d.name for d in outcome.devices]
        notes = []
        if outcome.missing:
            notes.append(f"not visible to Marusya: {', '.join(outcome.missing)}")
        if picked.skipped:
            notes.append(f"labeled but not supported: {', '.join(picked.skipped)}")
        detail = "; ".join(notes)
        return Status(state, detail, linked.config_name if linked else "", devices_seen, outcome.missing,
                      dt_util.utcnow())

    async def _hook_token(self) -> str:
        data = self._entry.data
        if data.get(CONF_HOOK_TOKEN) and hook_token.is_valid(self._hass, data.get(CONF_HOOK_REFRESH_TOKEN_ID)):
            return data[CONF_HOOK_TOKEN]
        await hook_token.async_revoke(self._hass, data.get(CONF_HOOK_USER_ID))
        issued = await hook_token.async_issue(self._hass, self._entry.title)
        self._update_data({CONF_HOOK_TOKEN: issued.token, CONF_HOOK_REFRESH_TOKEN_ID: issued.refresh_token_id,
                           CONF_HOOK_USER_ID: issued.user_id})
        return issued.token

    def _update_data(self, changes: dict) -> None:
        self._hass.config_entries.async_update_entry(self._entry, data={**self._entry.data, **changes})

    @callback
    def _set(self, status: Status) -> None:
        if status.state not in (STATE_SYNCING, STATE_LINKED, STATE_NO_DEVICES):
            _LOGGER.warning("%s: DIY %s — %s", self._entry.title, status.state, status.detail)
        self.status = status
        for listener in list(self._listeners):
            listener()


def account_entries(hass: HomeAssistant) -> list[ConfigEntry]:
    return [e for e in hass.config_entries.async_entries(DOMAIN)
            if e.data.get(KIND) == KIND_ACCOUNT and e.state is ConfigEntryState.LOADED]
