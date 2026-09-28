"""A local stand-in for vc.go.mail.ru: the Marusya server and the DIY cabinet, as seen live in 2026-09."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from urllib.parse import urlencode

import yaml
from aiohttp import web

from .pages import cabinet_page, choice_page

SH_DATA = "valid-sh-data"
FOREIGN_VK_TOKEN = "foreign"


def _error(status: int, code: int, reason: str) -> web.Response:
    return web.json_response({"code": code, "reason": reason}, status=status)


@dataclass
class FakeMarusya:
    configs: dict[str, tuple[str, str]] = field(default_factory=dict)
    sessions: dict[str, str] = field(default_factory=dict)
    linked: str | None = None
    pending_link: dict[str, str] = field(default_factory=dict)
    refuse_choice: set[str] = field(default_factory=set)
    csrf: str = ""
    removed: list[str] = field(default_factory=list)

    def add_config(self, name: str, text: str = "[]") -> str:
        config_id = str(uuid.uuid4())
        self.configs[config_id] = (name, text)
        return config_id

    def app(self) -> web.Application:
        app = web.Application()
        app.router.add_post("/registration/by_vk", self.by_vk)
        app.router.add_post("/registration/get_session", self.get_session)
        app.router.add_post("/account/vk/exchange_silent_token", self.exchange_silent_token)
        app.router.add_get("/smarthouse/api/widget/providers/", self.providers)
        app.router.add_get("/smarthouse/api/widget/index/", self.index)
        app.router.add_get("/smarthouse/api/diy/unlink/", self.unlink)
        app.router.add_get("/smarthouse/api/diy/link/", self.link)
        app.router.add_get("/smarthouse/diy/", self.cabinet)
        app.router.add_post("/smarthouse/diy/", self.upload)
        app.router.add_get("/smarthouse/diy/auth", self.choice)
        app.router.add_post("/smarthouse/diy/auth", self.choose)
        app.router.add_get("/smarthouse/diy/callback", self.callback)
        return app

    async def by_vk(self, request: web.Request) -> web.Response:
        if request.query["vk_access_token"] == FOREIGN_VK_TOKEN:
            return _error(500, 5010, "Registration error")
        return web.json_response({"result": {"status": "ready", "token": "reg-" + request.query["vk_user_id"]}})

    async def get_session(self, request: web.Request) -> web.Response:
        session_id, secret = f"sid-{uuid.uuid4().hex[:8]}", uuid.uuid4().hex
        self.sessions[session_id] = secret
        return web.json_response({"result": {"session_id": session_id, "session_secret": secret,
                                             "account_id": "acc", "new_account": False}})

    async def exchange_silent_token(self, request: web.Request) -> web.Response:
        return web.json_response({"result": {"access_token": "vk-from-silent", "user_id": 42}})

    def _session_ok(self, request: web.Request) -> bool:
        secret = self.sessions.get(request.query.get("session_id", ""))
        return secret is not None and request.headers.get("Authorization") == f"Bearer {secret}"

    async def providers(self, request: web.Request) -> web.Response:
        if not self._session_ok(request):
            return _error(403, 1001, "Authorization failed")
        return web.json_response([{"uid": "yandex", "is_auth": False},
                                  {"uid": "diy", "is_auth": self.linked is not None}])

    async def index(self, request: web.Request) -> web.Response:
        if not self._session_ok(request):
            return _error(403, 1001, "Authorization failed")
        devices = []
        if self.linked in self.configs:
            for item in yaml.safe_load(self.configs[self.linked][1]) or []:
                devices.append({"uid": f"diy|{item['id']}", "name": item["name"], "provider": "diy"})
        return web.json_response({"devices": devices})

    async def unlink(self, request: web.Request) -> web.Response:
        if not self._session_ok(request):
            return _error(403, 1001, "Authorization failed")
        self.linked = None
        return web.json_response({"success": True})

    async def link(self, request: web.Request) -> web.Response:
        if request.query.get("session_id") not in self.sessions:
            return _error(403, 1001, "Authorization failed")
        if self.linked is not None:
            return web.json_response({"error": "Conflict"}, status=409)
        state = uuid.uuid4().hex
        query = urlencode({"response_type": "code", "client_id": "diy", "state": state,
                           "redirect_uri": "https://vc.go.mail.ru/smarthouse/diy/callback"})
        raise web.HTTPFound(f"/smarthouse/diy/auth?{query}")

    def _cabinet_session(self, request: web.Request) -> None:
        if request.cookies.get("sh_data") != SH_DATA:
            raise web.HTTPFound(f"/smarthouse/diy/login?back={request.path_qs}")

    async def cabinet(self, request: web.Request) -> web.Response:
        self._cabinet_session(request)
        if "remove" in request.query:
            self.configs.pop(request.query["remove"], None)
            self.removed.append(request.query["remove"])
        self.csrf = uuid.uuid4().hex
        response = web.Response(text=cabinet_page([(i, n) for i, (n, _) in self.configs.items()], self.csrf),
                                content_type="text/html")
        response.set_cookie("_csrf_token", self.csrf, path="/")
        return response

    async def upload(self, request: web.Request) -> web.Response:
        self._cabinet_session(request)
        form = await request.post()
        if form.get("_csrf_token") != self.csrf or request.cookies.get("_csrf_token") != self.csrf:
            return web.json_response({"error": "Forbidden"}, status=403)
        upload = form["upload"]
        self.add_config(upload.filename, upload.file.read().decode())
        return web.Response(text=cabinet_page([(i, n) for i, (n, _) in self.configs.items()]),
                            content_type="text/html")

    async def choice(self, request: web.Request) -> web.Response:
        self._cabinet_session(request)
        return web.Response(text=choice_page([(i, n) for i, (n, _) in self.configs.items()]),
                            content_type="text/html")

    async def choose(self, request: web.Request) -> web.Response:
        self._cabinet_session(request)
        house = (await request.post())["house"]
        if house in self.refuse_choice or house not in self.configs:
            return web.Response(status=500, text="500: Internal Server Error")
        code = uuid.uuid4().hex
        self.pending_link[code] = house
        raise web.HTTPFound(f"/smarthouse/diy/callback?code={code}&state={request.query['state']}")

    async def callback(self, request: web.Request) -> web.Response:
        house = self.pending_link.pop(request.query.get("code", ""), None)
        if house is None:
            raise web.HTTPFound("/smarthouse/diy/login")
        self.linked = house
        raise web.HTTPFound("marusia://dl.marusia.mail.ru/smart_home/diy/callback?success=1")
