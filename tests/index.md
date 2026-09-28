# `tests/`

Как проверять — [`../docs/testing/`](../docs/testing/index.md). Запуск: `pytest`.

- `fake_marusya.py` — подставной сервер Маруси и кабинета DIY на `aiohttp.web`: сессии, провайдер
  `diy`, `unlink`/`link`, страница выбора, callback, загрузка с проверкой `_csrf_token`.
- `pages.py` — синтетические страницы кабинета с разметкой настоящих, без личных данных.
- `conftest.py` — подставной сервер, сессия с cookie для адреса-IP.
- `test_vk_login.py`, `test_diy_yaml.py` — разбор адреса входа, описание и сборка YAML.
- `test_clients.py` — клиенты сервера Маруси и кабинета против подставного сервера.
- `test_sync.py` — синхронизация: первая, без изменений, замена, откат, чужая привязка.
- `test_integration.py` — формы, загрузка записей, токен хуков, reauth — внутри Home Assistant.
