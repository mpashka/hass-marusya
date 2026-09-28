"""Client of the Marusya server: login by a VK token and the DIY provider of an account."""

# @tag:marusya-api
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import aiohttp

from .const import APP_VERSION, HOST, VK_APP_ID
from .vk_login import SilentToken, VkToken

TIMEOUT = aiohttp.ClientTimeout(total=30)
USER_AGENT = "okhttp/4.12.0"
SESSION_GONE_CODES = frozenset({1001, 4010, 4012})
DIY = "diy"


class MarusyaError(Exception):
    """The Marusya server refused `step`; `detail` says how, in the server's words."""

    def __init__(self, step: str, detail: str) -> None:
        super().__init__(f"{step}: {detail}")
        self.step = step
        self.detail = detail


class MarusyaSessionGone(MarusyaError):
    """The session is expired or invalid: a new VK login is required."""


@dataclass(frozen=True)
class Session:
    device_id: str
    session_id: str
    session_secret: str
    account_id: str
    vk_user_id: str
    new_account: bool = False


@dataclass(frozen=True)
class DiyDevice:
    uid: str
    name: str


def new_device_id() -> str:
    return ":c:m:android:" + uuid.uuid4().hex


class MarusyaClient:
    def __init__(self, http: aiohttp.ClientSession, session: Session | None = None) -> None:
        self._http = http
        self.session = session

    async def login(self, credential: VkToken | SilentToken, device_id: str | None = None) -> Session:
        device_id = device_id or new_device_id()
        if isinstance(credential, SilentToken):
            credential = await self._exchange_silent_token(credential, device_id)
        result = await self._call(
            "POST", "registration/by_vk", "registration/by_vk",
            {"device_id": device_id, "vk_access_token": credential.access_token, "vk_user_id": credential.user_id},
        )
        if not result.get("token"):
            raise MarusyaError("registration/by_vk", f"no registration token in {sorted(result)}")
        result = await self._call(
            "POST", "registration/get_session", "registration/get_session",
            {"device_id": device_id, "reg_token": result["token"], "with_secret": "1", "with_account_info": "1"},
        )
        if not result.get("session_id") or not result.get("session_secret"):
            raise MarusyaError("registration/get_session", f"no session in {sorted(result)}")
        self.session = Session(
            device_id=device_id,
            session_id=result["session_id"],
            session_secret=result["session_secret"],
            account_id=str(result.get("account_id", "")),
            vk_user_id=credential.user_id,
            new_account=bool(result.get("new_account")),
        )
        return self.session

    async def diy_is_linked(self) -> bool:
        providers = await self._widget("smarthouse/api/widget/providers/", "providers")
        diy = next((p for p in providers if isinstance(p, dict) and p.get("uid") == DIY), None)
        if diy is None:
            raise MarusyaError("providers", "no DIY provider in the provider list")
        return bool(diy.get("is_auth"))

    async def unlink_diy(self) -> None:
        body = await self._widget(f"smarthouse/api/{DIY}/unlink/", "unlink")
        if not (isinstance(body, dict) and body.get("success")):
            raise MarusyaError("unlink", f"unexpected answer {str(body)[:200]}")

    def diy_link_url(self) -> str:
        session = self._require_session()
        query = urlencode({"session_id": session.session_id, "device_id": session.device_id, "deeplink": "1"})
        return f"{HOST}/smarthouse/api/{DIY}/link/?{query}"

    async def diy_devices(self) -> list[DiyDevice]:
        index = await self._widget("smarthouse/api/widget/index/", "devices")
        return [
            DiyDevice(d["uid"], d.get("name", ""))
            for d in (index.get("devices") or [])
            if isinstance(d, dict) and d.get("provider") == DIY
        ]

    async def _exchange_silent_token(self, silent: SilentToken, device_id: str) -> VkToken:
        result = await self._call(
            "POST", "account/vk/exchange_silent_token", "exchange_silent_token",
            {"device_id": device_id, "token": silent.token, "uuid": silent.uuid, "app_id": VK_APP_ID},
        )
        if not result.get("access_token"):
            raise MarusyaError("exchange_silent_token", f"no access token in {sorted(result)}")
        return VkToken(result["access_token"], str(result.get("user_id") or silent.user_id))

    async def _call(self, method: str, path: str, step: str, params: dict[str, str]) -> dict[str, Any]:
        query = {"device_ver": APP_VERSION, **params, "client_request_id": str(uuid.uuid4())}
        async with self._http.request(
            method, f"{HOST}/{path}", params=query, timeout=TIMEOUT,
            headers={"Accept": "application/json", "User-Agent": USER_AGENT},
        ) as resp:
            body = await _json(resp, step)
        _raise_for_error(step, resp.status, body)
        result = body.get("result") if isinstance(body, dict) else None
        if not isinstance(result, dict):
            raise MarusyaError(step, f"HTTP {resp.status} without result")
        return result

    async def _widget(self, path: str, step: str) -> Any:
        session = self._require_session()
        params = {"device_id": session.device_id, "session_id": session.session_id,
                  "account_id": session.account_id, "ver": "v2"}
        async with self._http.get(
            f"{HOST}/{path}", params=params, timeout=TIMEOUT,
            headers={"Accept": "application/json", "Authorization": f"Bearer {session.session_secret}"},
        ) as resp:
            body = await _json(resp, step)
        _raise_for_error(step, resp.status, body)
        if resp.status != 200:
            raise MarusyaError(step, f"HTTP {resp.status}")
        return body

    def _require_session(self) -> Session:
        if self.session is None:
            raise MarusyaSessionGone("session", "no Marusya session: log in to VK first")
        return self.session


async def _json(resp: aiohttp.ClientResponse, step: str) -> Any:
    try:
        return await resp.json(content_type=None)
    except ValueError as err:
        raise MarusyaError(step, f"HTTP {resp.status}, not JSON") from err


def _raise_for_error(step: str, status: int, body: Any) -> None:
    if not isinstance(body, dict) or "code" not in body:
        return
    detail = f"HTTP {status}, code {body.get('code')}: {body.get('reason') or body.get('error')}"
    if body.get("code") in SESSION_GONE_CODES:
        raise MarusyaSessionGone(step, detail)
    raise MarusyaError(step, detail)
