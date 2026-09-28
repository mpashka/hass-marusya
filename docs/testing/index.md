# Проверка

Родитель: [`../index.md`](../index.md).

- **Модульные тесты** — `pytest` с `pytest-homeassistant-custom-component`, без внешней сети:
  сервер Маруси и кабинет — подставной сервер на `127.0.0.1` ([`../../tests/fake_marusya.py`](../../tests/index.md)),
  страницы кабинета — синтетические, с разметкой настоящих. Запуск:
  `python3 -m venv .venv && .venv/bin/pip install -r requirements-test.txt && .venv/bin/pytest`.
  `aioresponses` не годится: несовместим с aiohttp свежего Home Assistant (`stream_writer`).
- **hassfest локально** — `docker run --rm -v $PWD:/github/workspace ghcr.io/home-assistant/hassfest`.
- **CI** — `hassfest` и проверка HACS на каждый push.
- **Живая проверка** — только на одном аккаунте и с согласия владельца: синхронизация
  отвязывает DIY аккаунта. Признак успеха — сущность «Состояние DIY» `linked` и голосовое
  «включи <устройство>».
