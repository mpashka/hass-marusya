"""Parse the address a VK login ends on (oauth.vk.com/blank.html) into a VK credential."""

# @tag:vk-login
from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

BLANK_HOSTS = frozenset({"oauth.vk.com", "oauth.vk.ru"})


@dataclass(frozen=True)
class VkToken:
    access_token: str
    user_id: str


@dataclass(frozen=True)
class SilentToken:
    """VK ID login result: must be exchanged by the Marusya server within its ttl (600 s)."""

    token: str
    uuid: str
    user_id: str


class LoginAddressError(ValueError):
    """The pasted address is not a finished VK login; `reason` is a translation key."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def parse_login_address(address: str) -> VkToken | SilentToken:
    url = urlsplit(address.strip())
    if url.hostname not in BLANK_HOSTS or url.path != "/blank.html":
        raise LoginAddressError("not_blank_page")
    fragment = parse_qs(url.fragment)
    if "error" in fragment:
        raise LoginAddressError("vk_refused")
    if "access_token" in fragment:
        return VkToken(fragment["access_token"][0], fragment.get("user_id", [""])[0])
    if "payload" in fragment:
        try:
            payload = json.loads(fragment["payload"][0])
        except ValueError as err:
            raise LoginAddressError("payload_unreadable") from err
        if payload.get("type") != "silent_token" or not payload.get("token"):
            raise LoginAddressError("payload_unreadable")
        return SilentToken(payload["token"], payload.get("uuid", ""), str((payload.get("user") or {}).get("id", "")))
    raise LoginAddressError("no_token")
