import json
from urllib.parse import quote

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import label_registry as lr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.marusya_diy.const import (
    CONF_CONFIG_ID, CONF_HOOK_USER_ID, CONF_SH_DATA, DOMAIN, KIND, KIND_ACCOUNT, KIND_CABINET, OPT_BASE_URL,
    OPT_DEFAULT_ROOM, OPT_DEVICES, OPT_LABEL,
)

from .fake_marusya import FOREIGN_VK_TOKEN, SH_DATA

BLANK = "https://oauth.vk.com/blank.html#access_token={token}&expires_in=0&user_id=42"
DEVICES = "- {entity_id: input_boolean.kitchen_light, name: Свет, type: light}\n"


@pytest.fixture
async def lamp(hass: HomeAssistant):
    hass.states.async_set("input_boolean.kitchen_light", "off")


async def add_account(hass: HomeAssistant, token: str = "vk"):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "account"})
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "Kitchen", "address": BLANK.format(token=token)})


async def add_cabinet(hass: HomeAssistant, value: str):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "cabinet"})
    return await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_SH_DATA: value})


def sensor(hass: HomeAssistant):
    return hass.states.get("sensor.kitchen_diy_state")


async def test_account_flow_creates_entry(hass, fake, cabinet_http):
    result = await add_account(hass)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Kitchen"
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.unique_id == "42" and entry.data[KIND] == KIND_ACCOUNT
    await hass.async_block_till_done(wait_background_tasks=True)
    assert sensor(hass).state == "waiting_cabinet"


async def test_account_flow_names_refusals(hass, fake, cabinet_http):
    result = await add_account(hass, FOREIGN_VK_TOKEN)
    assert result["errors"] == {"address": "marusya_refused"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "Kitchen", "address": "https://example.com/"})
    assert result["errors"] == {"address": "not_blank_page"}


async def test_silent_token_of_vk_id_is_accepted(hass, fake, cabinet_http):
    payload = quote(json.dumps({"type": "silent_token", "token": "st", "uuid": "", "user": {"id": 42}}))
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "account"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "Kitchen", "address": f"https://oauth.vk.ru/blank.html#payload={payload}"})
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_cabinet_flow_takes_a_whole_cookie_header(hass, fake, cabinet_http):
    result = await add_cabinet(hass, "expired")
    assert result["errors"] == {CONF_SH_DATA: "cabinet_refused"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_SH_DATA: f"mrcu=1; sh_data={SH_DATA}; _csrf_token=x"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SH_DATA] == SH_DATA


async def test_devices_reach_marusya_and_the_hook_token_works(hass, fake, cabinet_http, lamp):
    await add_account(hass)
    await add_cabinet(hass, SH_DATA)
    await hass.async_block_till_done(wait_background_tasks=True)
    account = next(e for e in hass.config_entries.async_entries(DOMAIN) if e.data[KIND] == KIND_ACCOUNT)
    assert sensor(hass).state == "no_devices"

    result = await hass.config_entries.options.async_init(account.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {
        OPT_DEFAULT_ROOM: "Кухня", OPT_DEVICES: DEVICES, OPT_BASE_URL: "https://ha.example"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done(wait_background_tasks=True)

    state = sensor(hass)
    assert state.state == "linked", state.attributes
    assert state.attributes["devices"] == ["Свет"]
    assert fake.linked == account.data[CONF_CONFIG_ID]
    name, text = fake.configs[fake.linked]
    assert name == "hass-kitchen.yaml"
    assert "https://ha.example/api/services/input_boolean/turn_on" in text
    user = await hass.auth.async_get_user(account.data[CONF_HOOK_USER_ID])
    assert user is not None and not user.is_admin

    await hass.config_entries.async_remove(account.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert await hass.auth.async_get_user(account.data[CONF_HOOK_USER_ID]) is None
    assert fake.linked is None and fake.configs == {}


async def test_options_refuse_unknown_entities(hass, fake, cabinet_http):
    await add_account(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    account = hass.config_entries.async_entries(DOMAIN)[0]
    result = await hass.config_entries.options.async_init(account.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {OPT_DEFAULT_ROOM: "Кухня", OPT_DEVICES: DEVICES})
    assert result["errors"] == {OPT_DEVICES: "unknown_entities"}


async def test_expired_marusya_session_starts_reauth(hass, fake, cabinet_http, lamp):
    MockConfigEntry(domain=DOMAIN, unique_id="cabinet", data={KIND: KIND_CABINET, CONF_SH_DATA: SH_DATA}
                    ).add_to_hass(hass)
    account = MockConfigEntry(
        domain=DOMAIN, unique_id="42", title="Kitchen",
        data={KIND: KIND_ACCOUNT, "device_id": "dev", "session_id": "sid-gone", "session_secret": "s",
              "account_id": "acc", "vk_user_id": "42"},
        options={OPT_DEFAULT_ROOM: "Кухня", OPT_DEVICES: DEVICES, OPT_BASE_URL: "https://ha.example"})
    account.add_to_hass(hass)
    await hass.config_entries.async_setup(account.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert sensor(hass).state == "reauth"
    flows = hass.config_entries.flow.async_progress()
    assert [f["context"]["source"] for f in flows] == ["reauth"]
    result = await hass.config_entries.flow.async_configure(
        flows[0]["flow_id"], {"address": BLANK.format(token="vk")})
    assert result["reason"] == "reauth_successful"
    await hass.async_block_till_done(wait_background_tasks=True)
    assert sensor(hass).state == "linked"


async def test_labeling_an_entity_adds_it_to_the_speaker(hass, fake, cabinet_http):
    registry = er.async_get(hass)
    for object_id, name in (("kitchen", "Свет"), ("kettle", "Чайник")):
        registry.async_get_or_create("light", "test", object_id, suggested_object_id=object_id)
        hass.states.async_set(f"light.{object_id}", "off", {"friendly_name": name})
    label = lr.async_get(hass).async_create("Маруся: кухня")
    registry.async_update_entity("light.kitchen", labels={label.label_id})
    await add_account(hass)
    await add_cabinet(hass, SH_DATA)
    account = next(e for e in hass.config_entries.async_entries(DOMAIN) if e.data[KIND] == KIND_ACCOUNT)
    result = await hass.config_entries.options.async_init(account.entry_id)
    await hass.config_entries.options.async_configure(result["flow_id"], {
        OPT_DEFAULT_ROOM: "Кухня", OPT_LABEL: label.label_id, OPT_BASE_URL: "https://ha.example"})
    await hass.async_block_till_done(wait_background_tasks=True)
    assert sensor(hass).attributes["devices"] == ["Свет"]

    registry.async_update_entity("light.kettle", labels={label.label_id})
    await hass.async_block_till_done(wait_background_tasks=True)

    assert sensor(hass).state == "linked"
    assert sorted(sensor(hass).attributes["devices"]) == ["Свет", "Чайник"]
    assert "light/turn_on" in fake.configs[fake.linked][1]
