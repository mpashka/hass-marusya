---
tags: "@tag:marusya-api @tag:cabinet @tag:vk-login"
---

# Сервер Маруси и кабинет DIY: контракты

Родитель: [`index.md`](index.md).

Официального API нет. Всё ниже снято разбором приложения «Маруся» 1.91.5 (`jadx`) и проверено
живьём в сентябре 2026; непроверенное помечено. Хост — `https://vc.go.mail.ru`.

## Форма запроса к серверу Маруси

- Все параметры — в query-строке, в том числе у `POST`; тело пустое.
- В каждом запросе: `device_id`, `device_ver=1.91.5`, `client_request_id=<uuid4>`.
- `device_id` придумывает клиент и держит постоянным: `:c:m:android:<uuid4 без дефисов>`.
- После входа: `session_id=<…>` в query и `Authorization: Bearer <session_secret>`.
  Подписи запросов нет.
- Ответ — JSON, полезное в `result`. Ошибка — `code` и `reason`: `1001` — сессии нет или она
  негодна, `4010`/`4012` — сессия истекла (нужен новый вход), `4006` — клиент устарел,
  `4040` — слишком часто.
- `User-Agent` приложения — `okhttp/4.12.0`.

## Вход: токен VK → сессия Маруси {#vk-login}

1. Человек открывает
   `https://oauth.vk.com/authorize?client_id=6463690&redirect_uri=https://oauth.vk.com/blank.html&response_type=token&display=page&v=5.131`
   и входит. Вход кончается на одном из двух адресов, оба годятся:
   - `https://oauth.vk.com/blank.html#access_token=…&expires_in=…&user_id=…`;
   - `https://oauth.vk.ru/blank.html#payload={"type":"silent_token","token":…,"uuid":…,"ttl":600,"user":{"id":…}}`
     — вход через VK ID. Этот токен живёт 600 с и меняется без сессии:
     `POST account/vk/exchange_silent_token?token=…&uuid=…&app_id=6463690` →
     `result.access_token`, `result.user_id`. Обмен по коду приложения; живьём не проверен.
2. `POST registration/by_vk?vk_access_token=…&vk_user_id=…` → `result.token` (регистрационный).
   Принимает токен **только** приложения `6463690`; токен другого приложения — `500`,
   `code 5010 Registration error`.
3. `POST registration/get_session?reg_token=…&with_secret=1&with_account_info=1` →
   `result.session_id`, `result.session_secret`, `result.account_id`, `result.new_account`.
   `new_account: false` — аккаунт Маруси этого VK уже был, колонки его видны.

Срок жизни сессии неизвестен; ручки продления нет — при `4010`/`4012`/`1001` нужен новый вход.

## Умный дом аккаунта

Ручки мини-приложения «Умный дом». Кроме общей формы в query ещё `account_id` и `ver=v2`.

- `GET smarthouse/api/widget/providers/` — список провайдеров. У DIY `uid: diy`; привязан —
  `is_auth: true`, `url: /smarthouse/diy/unlink/`, иначе `url: /smarthouse/diy/link/`.
- `GET smarthouse/api/widget/index/` — дома, комнаты, колонки (`capsules`) и устройства.
  Устройство DIY — `uid: diy|<id из YAML>`, `provider: diy`.
- `GET smarthouse/api/diy/unlink/` → `200 {"success": true}`. Именно `GET`, как в мини-приложении.
- `GET smarthouse/api/diy/link/?session_id=…&device_id=…&deeplink=1` — начало привязки;
  авторизует её только `session_id`. У привязанного аккаунта — `409 Conflict`, поэтому
  перепривязка — это `unlink`, затем `link`.

## Кабинет DIY {#cabinet}

`https://vc.go.mail.ru/smarthouse/diy/` — серверные HTML-страницы. Сессия — cookie `sh_data`
(HttpOnly, Secure, 13 месяцев); без неё — `302 /smarthouse/diy/login?back=…`, это и есть признак
истёкшей сессии.

- **Список.** `GET /smarthouse/diy/` → форма загрузки и конфигурации: имя (= имя загруженного
  файла), дата, ссылка «Удалить» `?remove=<id>`. На каждый `GET` кабинет ставит новую cookie
  `_csrf_token` и сверяет её с полем формы: клиент обязан принимать `Set-Cookie`.
- **Загрузка.** `POST /smarthouse/diy/` `multipart/form-data`: `_csrf_token` из формы, `yaml=""`,
  `upload=<имя.yaml, содержимое>` → `200` со страницей кабинета. Одноимённый файл не заменяет
  конфигурацию, а добавляет вторую. Поле `yaml` (текст вместо файла) — путь приложения; какое
  имя получает конфигурация при нём, не проверено.
- **Удаление.** `GET /smarthouse/diy/?remove=<id>` → `200`.
- **Выбор при привязке.** Страница `/smarthouse/diy/auth?response_type=code&client_id=diy&redirect_uri=…/callback&state=<uuid>`
  под `sh_data` — список конфигураций, у каждой `data-link=<id>` (тот же id, что в `?remove=`).
  `POST` того же адреса с `house=<id>` → `302 /smarthouse/diy/callback?code=…&state=…`;
  `GET callback` → `302 marusia://…/smart_home/diy/callback?success=1` — привязка сделана,
  дальше идти не нужно.

Конфигурация кабинета одного аккаунта VK привязывается к аккаунту Маруси другого: кабинет
открывается сессией своего владельца, код уходит аккаунту, чья сессия пришла в `link`.

Открыто: держится ли привязка аккаунта к конфигурации, если конфигурацию удалить из кабинета, —
от этого зависит порядок «загрузить новую → перепривязать → удалить старую»
([`../implementation/sync.puml`](../implementation/sync.puml)).

## Формат конфигурации DIY

Список устройств YAML. У устройства `id`, `name`, `description`, `room`,
`type: devices.types.<тип>`, `custom_data`, `capabilities` — одна `devices.capabilities.on_off`
с `retrievable` и хуками `on`, `off`, `state`: `url`, `method`, `json`, `headers`. Хук `state`
отвечает телом `GET /api/states/<entity_id>` Home Assistant — при `retrievable: true` Маруся
читает по нему состояние. Типы — [`../../README.md`](../../README.md), «Типы устройств».
