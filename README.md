# hass-marusya

Управление Home Assistant голосом через умную колонку «Маруся»: конфигурация DIY-хуков, которые
Маруся отправляет в REST API Home Assistant.

Как это устроено и как настроить — статья на Хабре:
[Как подружить Марусю и Home Assistant](https://habr.com/ru/articles/649571/).

## Файлы

- [`marusya-bedroom-light.yaml`](marusya-bedroom-light.yaml) — включение и выключение света в
  спальне голосом. Перед загрузкой в приложение Маруси подставьте `{hass_server}` — адрес вашего
  Home Assistant — и `{long-living-token}` — долгосрочный токен доступа из профиля Home Assistant.
- [`example.yaml`](example.yaml) — пример от разработчиков Маруси: Philips Hue через IFTTT.

## Ограничение

DIY-хуки умеют только включать и выключать устройство. Прочитать через них состояние или
показание датчика из Home Assistant (например, температуру) нельзя.

## Типы устройств

- `devices.types.light` — свет
- `devices.types.socket` — розетка
- `devices.types.switch` — выключатель
- `devices.types.thermostat` — термостат
- `devices.types.thermostat.ac` — кондиционер
- `devices.types.media_device` — медиаустройство
- `devices.types.media_device.tv` — телевизор
- `devices.types.media_device.tv_box` — ТВ-приставка
- `devices.types.media_device.receiver` — ресивер
- `devices.types.cooking` — кухонная техника
- `devices.types.cooking.coffee_maker` — кофеварка
- `devices.types.cooking.kettle` — чайник
- `devices.types.cooking.multicooker` — мультиварка
- `devices.types.openable` — устройство с открытием
- `devices.types.openable.curtain` — штора
- `devices.types.humidifier` — увлажнитель
- `devices.types.purifier` — очиститель воздуха
- `devices.types.vacuum_cleaner` — пылесос
- `devices.types.washing_machine` — стиральная машина
- `devices.types.dishwasher` — посудомойка
- `devices.types.iron` — утюг
- `devices.types.sensor` — датчик
- `devices.types.other` — прочее устройство
