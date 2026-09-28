import pytest

from custom_components.marusya_diy.api import MarusyaClient, MarusyaError, MarusyaSessionGone, Session
from custom_components.marusya_diy.cabinet import Cabinet, CabinetError, CabinetSessionGone, parse_configs
from custom_components.marusya_diy.vk_login import SilentToken, VkToken

from .fake_marusya import FOREIGN_VK_TOKEN, SH_DATA
from .pages import cabinet_page, choice_page


async def login(http) -> MarusyaClient:
    client = MarusyaClient(http)
    await client.login(VkToken("vk", "42"), "dev")
    return client


async def test_login_by_access_token(fake, http):
    session = (await login(http)).session
    assert session.device_id == "dev" and session.vk_user_id == "42"
    assert session.session_id in fake.sessions


async def test_login_exchanges_silent_token_first(fake, http):
    session = await MarusyaClient(http).login(SilentToken("st", "", "42"))
    assert session.vk_user_id == "42"
    assert session.device_id.startswith(":c:m:android:")


async def test_foreign_token_is_refused_with_server_words(fake, http):
    with pytest.raises(MarusyaError) as err:
        await MarusyaClient(http).login(VkToken(FOREIGN_VK_TOKEN, "42"))
    assert err.value.step == "registration/by_vk"
    assert "5010" in err.value.detail


async def test_unknown_session_asks_for_login(fake, http):
    with pytest.raises(MarusyaSessionGone):
        await MarusyaClient(http, Session("dev", "sid-gone", "s", "acc", "42")).diy_is_linked()


async def test_whole_link_cycle(fake, http):
    client = await login(http)
    cabinet = Cabinet(http, SH_DATA)
    fake.linked = fake.add_config("manual.yaml")

    config = await cabinet.upload("hass-kitchen.yaml", "- {id: lamp, name: Свет}\n")
    assert await client.diy_is_linked()
    with pytest.raises(CabinetError, match="409"):
        await cabinet.choose(client.diy_link_url(), config.id)
    await client.unlink_diy()
    await cabinet.choose(client.diy_link_url(), config.id)

    assert fake.linked == config.id
    assert [(d.uid, d.name) for d in await client.diy_devices()] == [("diy|lamp", "Свет")]
    await cabinet.remove(config.id)
    assert config.id not in {c.id for c in await cabinet.configs()}


async def test_same_name_uploads_twice(fake, http):
    cabinet = Cabinet(http, SH_DATA)
    first = await cabinet.upload("hass-kitchen.yaml", "[]")
    second = await cabinet.upload("hass-kitchen.yaml", "[]")
    assert first.id != second.id
    assert [c.name for c in await cabinet.configs()] == ["hass-kitchen.yaml"] * 2


async def test_expired_cabinet_session(fake, http):
    with pytest.raises(CabinetSessionGone):
        await Cabinet(http, "expired").configs()


async def test_choose_refuses_config_missing_from_choice(fake, http):
    client = await login(http)
    with pytest.raises(CabinetError, match="choice page"):
        await Cabinet(http, SH_DATA).choose(client.diy_link_url(), "00000000-0000-0000-0000-000000000000")


def test_parse_configs_of_both_pages():
    configs = [("11111111-1111-1111-1111-111111111111", "hass-kitchen.yaml"),
               ("22222222-2222-2222-2222-222222222222", "other.yaml")]
    assert [(c.id, c.name) for c in parse_configs(cabinet_page(configs))] == configs
    assert [(c.id, c.name) for c in parse_configs(choice_page(configs))] == configs
