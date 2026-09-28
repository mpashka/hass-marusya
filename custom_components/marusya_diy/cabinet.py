"""Client of the DIY cabinet: server-rendered pages opened by the `sh_data` cookie."""

# @tag:cabinet
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import aiohttp
from yarl import URL

from .const import HOST

TIMEOUT = aiohttp.ClientTimeout(total=60)
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140 Safari/537.36"
CABINET_PATH = "/smarthouse/diy/"
LOGIN_PATH = "/smarthouse/diy/login"
AUTH_PATH = "/smarthouse/diy/auth"
CALLBACK_PATH = "/smarthouse/diy/callback"
MAX_REDIRECTS = 10

_ITEM_SPLIT = 'class="all-sk__item"'
_NAME = re.compile(r'all-sk__item-name">\s*([^<]*?)\s*</div>')
_DATE = re.compile(r'all-sk__item-desc">\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2})')
_ID = re.compile(r'(?:\?remove=|data-link=")([0-9a-f-]{36})')
_CSRF = re.compile(r'name="_csrf_token"[^>]*value="([^"]+)"|value="([^"]+)"[^>]*name="_csrf_token"')


class CabinetError(Exception):
    """The cabinet refused `step`; `detail` says how."""

    def __init__(self, step: str, detail: str) -> None:
        super().__init__(f"{step}: {detail}")
        self.step = step
        self.detail = detail


class CabinetSessionGone(CabinetError):
    """The cabinet sends to its login page: the `sh_data` cookie is expired or wrong."""


@dataclass(frozen=True)
class CabinetConfig:
    id: str
    name: str
    uploaded: str


def parse_configs(html: str) -> list[CabinetConfig]:
    """Configurations on the cabinet page or on the choice page of a link."""
    configs = []
    for item in html.split(_ITEM_SPLIT)[1:]:
        name, date, config_id = _NAME.search(item), _DATE.search(item), _ID.search(item)
        if name and date and config_id:
            configs.append(CabinetConfig(config_id.group(1), name.group(1), date.group(1)))
    return configs


class Cabinet:
    """One cabinet session; operations run one at a time because the page CSRF token is a shared cookie."""

    def __init__(self, http: aiohttp.ClientSession, sh_data: str) -> None:
        self._http = http
        self._lock = asyncio.Lock()
        http.cookie_jar.update_cookies({"sh_data": sh_data}, URL(HOST + "/"))

    async def configs(self) -> list[CabinetConfig]:
        async with self._lock:
            return parse_configs(await self._page("list"))

    async def upload(self, name: str, text: str) -> CabinetConfig:
        """Upload a configuration file; the cabinet adds it even if the name is taken."""
        async with self._lock:
            page = await self._page("upload")
            before = {c.id for c in parse_configs(page)}
            form = aiohttp.FormData()
            form.add_field("_csrf_token", _csrf(page))
            form.add_field("yaml", "")
            form.add_field("upload", text.encode(), filename=name, content_type="application/x-yaml")
            async with self._http.post(
                HOST + CABINET_PATH, data=form, allow_redirects=False, timeout=TIMEOUT, headers=self._headers(),
            ) as resp:
                _check_session("upload", resp)
                if resp.status != 200:
                    raise CabinetError("upload", f"HTTP {resp.status}")
            added = [c for c in parse_configs(await self._page("upload")) if c.id not in before and c.name == name]
            if len(added) != 1:
                raise CabinetError("upload", f"expected one new configuration {name}, found {len(added)}")
            return added[0]

    async def remove(self, config_id: str) -> None:
        async with self._lock:
            async with self._http.get(
                HOST + CABINET_PATH, params={"remove": config_id}, allow_redirects=False, timeout=TIMEOUT,
                headers=self._headers(),
            ) as resp:
                _check_session("remove", resp)
                if resp.status != 200:
                    raise CabinetError("remove", f"HTTP {resp.status}")

    async def choose(self, link_url: str, config_id: str) -> None:
        """Walk a provider link started by the Marusya server: choose the configuration, pass the callback."""
        async with self._lock:
            url, resp_text = await self._follow(link_url, "link", until_path=AUTH_PATH)
            if config_id not in {c.id for c in parse_configs(resp_text)}:
                raise CabinetError("choose", "the configuration is not on the choice page")
            async with self._http.post(
                url, data={"house": config_id}, allow_redirects=False, timeout=TIMEOUT, headers=self._headers(),
            ) as resp:
                _check_session("choose", resp)
                location = resp.headers.get("Location", "")
                if resp.status != 302 or CALLBACK_PATH not in location:
                    raise CabinetError("choose", f"HTTP {resp.status}, no code for the callback")
            final, _ = await self._follow(urljoin(url, location), "callback", until_path=None)
            if "success=1" not in urlsplit(final).query:
                raise CabinetError("callback", f"the link did not finish with success: {urlsplit(final)._replace(query='').geturl()}")

    async def _page(self, step: str) -> str:
        async with self._http.get(
            HOST + CABINET_PATH, allow_redirects=False, timeout=TIMEOUT, headers=self._headers(),
        ) as resp:
            _check_session(step, resp)
            if resp.status != 200:
                raise CabinetError(step, f"HTTP {resp.status}")
            return await resp.text()

    async def _follow(self, url: str, step: str, until_path: str | None) -> tuple[str, str]:
        """Follow redirects by hand: the chain ends on a `marusia://` deep link aiohttp cannot open."""
        for _ in range(MAX_REDIRECTS):
            if not url.startswith("http"):
                return url, ""
            async with self._http.get(url, allow_redirects=False, timeout=TIMEOUT, headers=self._headers()) as resp:
                _check_session(step, resp)
                location = resp.headers.get("Location")
                if resp.status in (301, 302, 303, 307) and location:
                    url = urljoin(url, location)
                    continue
                if resp.status == 409:
                    raise CabinetError(step, "the account already has DIY linked (HTTP 409)")
                if resp.status != 200 or (until_path and urlsplit(url).path != until_path):
                    raise CabinetError(step, f"HTTP {resp.status} at {urlsplit(url).path}")
                return url, await resp.text()
        raise CabinetError(step, f"more than {MAX_REDIRECTS} redirects")

    @staticmethod
    def _headers() -> dict[str, str]:
        return {"User-Agent": USER_AGENT, "Referer": HOST + CABINET_PATH, "Origin": HOST}


def _check_session(step: str, resp: aiohttp.ClientResponse) -> None:
    if resp.status in (301, 302, 303) and urlsplit(resp.headers.get("Location", "")).path == LOGIN_PATH:
        raise CabinetSessionGone(step, "the cabinet asks to log in: the sh_data cookie is expired or wrong")


def _csrf(page: str) -> str:
    match = _CSRF.search(page)
    if not match:
        raise CabinetError("upload", "no _csrf_token on the cabinet page")
    return next(group for group in match.groups() if group)

