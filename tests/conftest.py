import aiohttp
import pytest
from aiohttp.test_utils import TestServer

from custom_components.marusya_diy import api, cabinet

from .fake_marusya import FakeMarusya


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
async def fake(monkeypatch, socket_enabled):
    marusya = FakeMarusya()
    server = TestServer(marusya.app(), host="127.0.0.1")
    await server.start_server()
    base = str(server.make_url("")).rstrip("/")
    monkeypatch.setattr(api, "HOST", base)
    monkeypatch.setattr(cabinet, "HOST", base)
    marusya.base = base
    yield marusya
    await server.close()


@pytest.fixture
async def http():
    """IP-address cookies (the fake server) need an unsafe jar; the real host is a domain."""
    async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True)) as session:
        yield session


@pytest.fixture
def cabinet_http(monkeypatch, hass):
    """Integration code builds the cabinet session itself; give it the jar the fake server needs."""
    from homeassistant.helpers.aiohttp_client import async_create_clientsession

    import custom_components.marusya_diy as integration
    from custom_components.marusya_diy import config_flow, runtime

    def unsafe_jar(hass_):
        return async_create_clientsession(hass_, auto_cleanup=False, cookie_jar=aiohttp.CookieJar(unsafe=True))

    monkeypatch.setattr(runtime, "new_cabinet_http", unsafe_jar)
    monkeypatch.setattr(config_flow, "new_cabinet_http", unsafe_jar)
    monkeypatch.setattr(integration, "new_cabinet_http", unsafe_jar)
