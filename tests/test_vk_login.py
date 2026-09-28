import json
from urllib.parse import quote

import pytest

from custom_components.marusya_diy.vk_login import LoginAddressError, SilentToken, VkToken, parse_login_address


def test_access_token_address():
    address = "https://oauth.vk.com/blank.html#access_token=vk1.a.tok&expires_in=0&user_id=42"
    assert parse_login_address(address) == VkToken("vk1.a.tok", "42")


def test_silent_token_address_of_vk_id():
    payload = {"type": "silent_token", "token": "st", "uuid": "u", "ttl": 600, "user": {"id": 42}}
    address = "https://oauth.vk.ru/blank.html#payload=" + quote(json.dumps(payload))
    assert parse_login_address(f"  {address}\n") == SilentToken("st", "u", "42")


@pytest.mark.parametrize(("address", "reason"), [
    ("https://example.com/blank.html#access_token=t", "not_blank_page"),
    ("https://oauth.vk.com/authorize?client_id=6463690", "not_blank_page"),
    ("https://oauth.vk.com/blank.html#error=access_denied", "vk_refused"),
    ("https://oauth.vk.com/blank.html#payload=%7Bbroken", "payload_unreadable"),
    ("https://oauth.vk.com/blank.html#payload=" + quote('{"type": "other"}'), "payload_unreadable"),
    ("https://oauth.vk.com/blank.html", "no_token"),
])
def test_refused_addresses(address, reason):
    with pytest.raises(LoginAddressError) as err:
        parse_login_address(address)
    assert err.value.reason == reason
