import pytest

from custom_components.marusya_diy.api import MarusyaClient
from custom_components.marusya_diy.cabinet import Cabinet, CabinetSessionGone
from custom_components.marusya_diy.sync import (
    STATE_LINKED, STATE_NO_DEVICES, STATE_UNCHANGED, SyncError, async_sync,
)
from custom_components.marusya_diy.vk_login import VkToken

from .fake_marusya import SH_DATA

NAME = "hass-kitchen.yaml"
LAMP = "- {id: lamp, name: Свет}\n"
LAMP_AND_KETTLE = LAMP + "- {id: kettle, name: Чайник}\n"


@pytest.fixture
async def parts(fake, http):
    client = MarusyaClient(http)
    await client.login(VkToken("vk", "42"), "dev")
    return client, Cabinet(http, SH_DATA)


async def test_first_sync_replaces_a_manual_link_and_keeps_its_file(fake, parts):
    client, cabinet = parts
    manual = fake.add_config("marusya-kitchen.yaml")
    fake.linked = manual

    outcome = await async_sync(client, cabinet, NAME, LAMP, ["lamp"], previous=None)

    assert outcome.state == STATE_LINKED
    assert fake.linked == outcome.linked.config_id
    assert [d.uid for d in outcome.devices] == ["diy|lamp"] and outcome.missing == []
    assert manual in fake.configs


async def test_unchanged_description_touches_nothing(fake, parts):
    client, cabinet = parts
    first = await async_sync(client, cabinet, NAME, LAMP, ["lamp"], previous=None)
    configs_before = dict(fake.configs)

    again = await async_sync(client, cabinet, NAME, LAMP, ["lamp"], previous=first.linked)

    assert again.state == STATE_UNCHANGED
    assert fake.configs == configs_before


async def test_change_links_the_new_and_drops_the_old(fake, parts):
    client, cabinet = parts
    first = await async_sync(client, cabinet, NAME, LAMP, ["lamp"], previous=None)

    second = await async_sync(client, cabinet, NAME, LAMP_AND_KETTLE, ["lamp", "kettle"], previous=first.linked)

    assert fake.linked == second.linked.config_id != first.linked.config_id
    assert list(fake.configs) == [second.linked.config_id]
    assert sorted(d.uid for d in second.devices) == ["diy|kettle", "diy|lamp"]


async def test_refused_link_returns_the_previous_configuration(fake, parts):
    client, cabinet = parts
    first = await async_sync(client, cabinet, NAME, LAMP, ["lamp"], previous=None)
    original_add = fake.add_config

    def add_refused(name, text="[]"):
        config_id = original_add(name, text)
        fake.refuse_choice.add(config_id)
        return config_id

    fake.add_config = add_refused
    with pytest.raises(SyncError) as err:
        await async_sync(client, cabinet, NAME, LAMP_AND_KETTLE, ["lamp", "kettle"], previous=first.linked)

    assert err.value.rolled_back is True
    assert fake.linked == first.linked.config_id
    assert list(fake.configs) == [first.linked.config_id]


async def test_no_devices_leaves_a_foreign_link_alone(fake, parts):
    client, cabinet = parts
    fake.linked = fake.add_config("marusya-kitchen.yaml")

    outcome = await async_sync(client, cabinet, NAME, "[]\n", [], previous=None)

    assert outcome.state == STATE_NO_DEVICES
    assert fake.linked is not None


async def test_no_devices_undoes_our_own_link(fake, parts):
    client, cabinet = parts
    first = await async_sync(client, cabinet, NAME, LAMP, ["lamp"], previous=None)

    outcome = await async_sync(client, cabinet, NAME, "[]\n", [], previous=first.linked)

    assert outcome.state == STATE_NO_DEVICES
    assert fake.linked is None and fake.configs == {}


async def test_devices_marusya_does_not_show_are_named(fake, parts):
    client, cabinet = parts
    outcome = await async_sync(client, cabinet, NAME, LAMP, ["lamp", "ghost"], previous=None)
    assert outcome.missing == ["ghost"]


async def test_expired_cabinet_session_propagates(fake, http, parts):
    client, _ = parts
    with pytest.raises(CabinetSessionGone):
        await async_sync(client, Cabinet(http, "expired"), NAME, LAMP, ["lamp"], previous=None)
