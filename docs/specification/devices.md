---
tags: "@tag:diy-sync"
---

# Описание устройств

Родитель: [`index.md`](index.md).

Описание устройств — параметр записи аккаунта колонки (options flow): какие сущности Home
Assistant видит колонка этого аккаунта и под какими именами. Секретов в нём нет: адрес Home
Assistant и токен хуков интеграция подставляет сама.

## Формат

Два поля формы «Настроить»:

- `default_room` — комната по умолчанию, строка.
- `devices` — YAML-список устройств:

```yaml
- entity_id: input_boolean.kitchen_light_onoff
  name: Свет
  description: Свет на кухне    # необязательно; умолчание — name
  type: light                   # devices.types.<type>
  room: Гостиная                # необязательно; умолчание — default_room
  id: kitchen_light             # необязательно; умолчание — object_id сущности
- entity_id: script.cat_feed
  name: Корм кота
  type: other
  service: script/turn_on       # необязательно: одно действие вместо вкл/выкл/состояния
```

- Без `service` устройство получает хуки `on` и `off` — службы `<домен>.turn_on` и
  `<домен>.turn_off` домена сущности — и `state`, `retrievable: true`.
- С `service` — один хук `on`, вызывающий эту службу для сущности, `retrievable: false`.
- Проверка при отправке формы: сущность существует, `type` из перечня DIY, `id` уникальны.
  Ошибка — у поля формы, словами: какое устройство и что не так.

## Как задаёт скрипт

Через REST API Home Assistant, тем же options flow, что и человек (нужен токен администратора
Home Assistant):

```
POST /api/config/config_entries/options/flow        {"handler": "<entry_id>"}
POST /api/config/config_entries/options/flow/<flow_id>  {"default_room": "Кухня", "devices": "<YAML>"}
```

Ответ `type: create_entry` — принято; `type: form` с `errors` — отказ с причиной. Сохранение
перезагружает запись, и синхронизация идёт сама. Найти `entry_id` аккаунта —
`GET /api/config/config_entries/entry?domain=marusya_diy`, поле `title`.
