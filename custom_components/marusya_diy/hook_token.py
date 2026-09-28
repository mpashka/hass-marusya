"""A non-admin Home Assistant user per account whose long-lived token signs the DIY hooks."""

# @tag:hook-token
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from homeassistant.auth.const import GROUP_ID_USER
from homeassistant.core import HomeAssistant

TOKEN_LIFETIME = timedelta(days=3650)


@dataclass(frozen=True)
class HookToken:
    token: str
    refresh_token_id: str
    user_id: str


async def async_issue(hass: HomeAssistant, name: str) -> HookToken:
    user = await hass.auth.async_create_system_user(f"Marusya DIY: {name}", group_ids=[GROUP_ID_USER])
    refresh_token = await hass.auth.async_create_refresh_token(user, access_token_expiration=TOKEN_LIFETIME)
    return HookToken(hass.auth.async_create_access_token(refresh_token), refresh_token.id, user.id)


def is_valid(hass: HomeAssistant, refresh_token_id: str | None) -> bool:
    return bool(refresh_token_id) and hass.auth.async_get_refresh_token(refresh_token_id) is not None


async def async_revoke(hass: HomeAssistant, user_id: str | None) -> None:
    if user_id and (user := await hass.auth.async_get_user(user_id)) is not None:
        await hass.auth.async_remove_user(user)
