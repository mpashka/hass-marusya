"""Entries: an account of a speaker (VK login by a pasted address) and the DIY cabinet session."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    EntitySelector, EntitySelectorConfig, LabelSelector, TextSelector, TextSelectorConfig, TextSelectorType,
)
from homeassistant.util import dt as dt_util

from .api import MarusyaClient, MarusyaError, Session
from .cabinet import Cabinet, CabinetError, CabinetSessionGone
from .const import (
    CABINET_UNIQUE_ID, CONF_ACCOUNT_ID, CONF_DEVICE_ID, CONF_SESSION_ID, CONF_SESSION_SECRET, CONF_SH_DATA,
    CONF_SH_DATA_SET, CONF_VK_USER_ID, DOMAIN, KIND, KIND_ACCOUNT, KIND_CABINET, OPT_BASE_URL,
    OPT_DEFAULT_ROOM, OPT_DEVICES, OPT_ENTITIES, OPT_LABEL, VK_LOGIN_URL,
)
from .diy_yaml import DevicesError
from .entity_devices import PICKABLE_DOMAINS, account_devices
from .runtime import new_cabinet_http
from .vk_login import LoginAddressError, parse_login_address

ADDRESS = "address"
NAME = "name"
_SH_DATA = re.compile(r"(?:^|[;\s])sh_data=([^;\s]+)")

CABINET_URL = "https://vc.go.mail.ru/smarthouse/diy/"
FORMAT_URL = "https://github.com/mpashka/hass-marusya/blob/master/docs/specification/devices.md"

_ADDRESS_SCHEMA = vol.Schema({vol.Required(ADDRESS): TextSelector(TextSelectorConfig(type=TextSelectorType.URL))})
_CABINET_SCHEMA = vol.Schema(
    {vol.Required(CONF_SH_DATA): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))}
)


def _session_data(session: Session) -> dict[str, str]:
    return {CONF_DEVICE_ID: session.device_id, CONF_SESSION_ID: session.session_id,
            CONF_SESSION_SECRET: session.session_secret, CONF_ACCOUNT_ID: session.account_id,
            CONF_VK_USER_ID: session.vk_user_id}


def _sh_data_value(pasted: str) -> str:
    """Accept the bare value, `sh_data=…` or a whole Cookie header copied from DevTools."""
    pasted = pasted.strip()
    match = _SH_DATA.search(pasted)
    return match.group(1) if match else pasted


class MarusyaDiyConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return DevicesOptionsFlow()

    @classmethod
    @callback
    def async_supports_options_flow(cls, config_entry: ConfigEntry) -> bool:
        return config_entry.data.get(KIND) == KIND_ACCOUNT

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="user", menu_options=["account", "cabinet"])

    async def async_step_account(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            session, errors = await self._login(user_input[ADDRESS])
            if session is not None:
                await self.async_set_unique_id(session.vk_user_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=user_input[NAME].strip(),
                                               data={KIND: KIND_ACCOUNT, **_session_data(session)})
        schema = vol.Schema({vol.Required(NAME): str}).extend(_ADDRESS_SCHEMA.schema)
        return self.async_show_form(step_id="account", data_schema=self.add_suggested_values_to_schema(
            schema, user_input or {}), errors=errors, description_placeholders={"login_url": VK_LOGIN_URL})

    async def async_step_cabinet(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        await self.async_set_unique_id(CABINET_UNIQUE_ID)
        self._abort_if_unique_id_configured()
        errors: dict[str, str] = {}
        if user_input is not None:
            sh_data = _sh_data_value(user_input[CONF_SH_DATA])
            errors = await self._check_cabinet(sh_data)
            if not errors:
                return self.async_create_entry(title="DIY cabinet", data=self._cabinet_data(sh_data))
        return self.async_show_form(step_id="cabinet", data_schema=_CABINET_SCHEMA, errors=errors,
                                    description_placeholders={"cabinet_url": CABINET_URL})

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        if entry_data.get(KIND) == KIND_CABINET:
            return await self.async_step_reauth_cabinet()
        return await self.async_step_reauth_account()

    async def async_step_reauth_account(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            session, errors = await self._login(user_input[ADDRESS], entry.data.get(CONF_DEVICE_ID))
            if session is not None:
                if session.vk_user_id != entry.unique_id:
                    errors[ADDRESS] = "wrong_account"
                else:
                    return self.async_update_reload_and_abort(entry, data_updates=_session_data(session))
        return self.async_show_form(step_id="reauth_account", data_schema=_ADDRESS_SCHEMA, errors=errors,
                                    description_placeholders={"login_url": VK_LOGIN_URL, "name": entry.title})

    async def async_step_reauth_cabinet(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            sh_data = _sh_data_value(user_input[CONF_SH_DATA])
            errors = await self._check_cabinet(sh_data)
            if not errors:
                return self.async_update_reload_and_abort(self._get_reauth_entry(),
                                                          data_updates=self._cabinet_data(sh_data))
        return self.async_show_form(step_id="reauth_cabinet", data_schema=_CABINET_SCHEMA, errors=errors,
                                    description_placeholders={"cabinet_url": CABINET_URL})

    async def _login(self, address: str, device_id: str | None = None) -> tuple[Session | None, dict[str, str]]:
        try:
            credential = parse_login_address(address)
        except LoginAddressError as err:
            return None, {ADDRESS: err.reason}
        client = MarusyaClient(async_get_clientsession(self.hass))
        try:
            return await client.login(credential, device_id), {}
        except MarusyaError:
            return None, {ADDRESS: "marusya_refused"}
        except (aiohttp.ClientError, TimeoutError):
            return None, {"base": "cannot_connect"}

    async def _check_cabinet(self, sh_data: str) -> dict[str, str]:
        http = new_cabinet_http(self.hass)
        try:
            await Cabinet(http, sh_data).configs()
        except CabinetSessionGone:
            return {CONF_SH_DATA: "cabinet_refused"}
        except (CabinetError, aiohttp.ClientError, TimeoutError):
            return {"base": "cannot_connect"}
        finally:
            http.detach()
        return {}

    @staticmethod
    def _cabinet_data(sh_data: str) -> dict[str, str]:
        return {KIND: KIND_CABINET, CONF_SH_DATA: sh_data, CONF_SH_DATA_SET: dt_util.utcnow().isoformat()}


class DevicesOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        placeholders = {"where": "", "format_url": FORMAT_URL}
        if user_input is not None:
            try:
                devices = account_devices(self.hass, user_input).devices
            except DevicesError as err:
                errors[OPT_DEVICES], placeholders["where"] = err.reason, err.where
            else:
                unknown = [d.entity_id for d in devices if self.hass.states.get(d.entity_id) is None]
                if unknown:
                    errors[OPT_DEVICES], placeholders["where"] = "unknown_entities", ", ".join(unknown)
            if not errors:
                return self.async_create_entry(data=user_input)
        schema = vol.Schema({
            vol.Optional(OPT_DEFAULT_ROOM, default=""): str,
            vol.Optional(OPT_LABEL): LabelSelector(),
            vol.Optional(OPT_ENTITIES, default=[]): EntitySelector(
                EntitySelectorConfig(domain=PICKABLE_DOMAINS, multiple=True)),
            vol.Optional(OPT_DEVICES, default=""): TextSelector(TextSelectorConfig(multiline=True)),
            vol.Optional(OPT_BASE_URL): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
        })
        return self.async_show_form(
            step_id="init", errors=errors, description_placeholders=placeholders,
            data_schema=self.add_suggested_values_to_schema(schema, user_input or self.config_entry.options),
        )
