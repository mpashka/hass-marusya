---
tags: "@tag:diy-sync @tag:marusya-api @tag:cabinet @tag:vk-login @tag:hook-token"
---

# `custom_components/marusya_diy/`

Интеграция Home Assistant. Устройство — [`../../docs/implementation/`](../../docs/implementation/index.md).

- `__init__.py` — загрузка, выгрузка и удаление записей.
- `config_flow.py` — формы: аккаунт колонки, сессия кабинета, reauth обоих, описание устройств.
- `runtime.py` — работа загруженных записей: сессия кабинета, состояние и синхронизация аккаунта.
- `sync.py` — синхронизация аккаунта с описанием устройств.
- `api.py` — клиент сервера Маруси.
- `cabinet.py` — клиент кабинета DIY.
- `vk_login.py` — разбор адреса, которым кончается вход в VK.
- `diy_yaml.py` — описание устройств: проверка и сборка конфигурации DIY.
- `entity_devices.py` — устройства аккаунта: YAML плюс сущности с меткой и из списка.
- `hook_token.py` — служебный пользователь и токен хуков.
- `sensor.py` — сущность «Состояние DIY».
- `const.py` — имена и адреса.
- `manifest.json`, `strings.json`, `translations/` — описание интеграции для Home Assistant, тексты en/ru.
- `brand/` — значок (`icon.png` 256, `icon@2x.png` 512): знак Маруси с сайта marusia.vk.com; HA ≥ 2026.3 берёт его отсюда, HACS проверяет его наличие.
