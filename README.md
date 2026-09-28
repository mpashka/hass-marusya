# hass-marusya

Управление Home Assistant голосом через умную колонку «Маруся» — DIY Hooks: по голосовой
команде облако Маруси вызывает REST API Home Assistant.

## Интеграция `marusya_diy` — без мобильного приложения

Раньше колонку подключали через приложение «Маруся» на телефоне: вход в VK, загрузка YAML в
кабинет DIY, «Выбрать». Интеграция делает это из Home Assistant: человек по разу входит в VK на
каждый аккаунт колонки и раз в 13 месяцев вставляет сессию кабинета, остальное — сборку YAML,
загрузку, привязку и обновление при смене устройств — интеграция делает сама. Колонки на разных
аккаунтах VK получают каждая свой набор устройств.

⚠ Протокол неофициальный — разобран по приложению «Маруся» 1.91.5; сервер может его поменять.

### Установка

1. HACS → «Пользовательские репозитории» → `https://github.com/mpashka/hass-marusya`, категория
   «Интеграция» → установить «Marusya DIY» → перезапустить Home Assistant.
2. Настройки → Устройства и службы → «Добавить интеграцию» → Marusya DIY → **«Сессия кабинета DIY»**:
   войти на `vc.go.mail.ru/smarthouse/diy/` в браузере, в DevTools → Application → Cookies
   скопировать значение `sh_data` и вставить.
3. Ещё раз «Добавить интеграцию» → Marusya DIY → **«Аккаунт колонки»**: открыть ссылку входа в VK,
   войти под аккаунтом VK колонки, скопировать адрес пустой страницы `oauth.vk.com/blank.html…`
   (или `oauth.vk.ru/…`) и вставить. Повторить для каждого аккаунта.
4. На записи аккаунта — «Настроить»: список устройств YAML
   ([формат](docs/specification/devices.md)). Через несколько секунд сущность «Состояние DIY»
   станет «Привязано», и колонка отзовётся на «включи свет».

У Home Assistant должен быть внешний адрес `https` (Настройки → Система → Сеть) или адрес в
параметре `base_url` записи: по нему облако Маруси зовёт хуки. Токен для хуков интеграция
заводит сама — отдельного пользователя без прав администратора на каждый аккаунт.

Описание устройств можно задавать скриптом через REST API Home Assistant — тот же «Настроить»,
см. [формат](docs/specification/devices.md#как-задаёт-скрипт).

Как устроено — [`docs/`](docs/index.md).

## Файлы для ручной загрузки

- [`marusya-bedroom-light.yaml`](marusya-bedroom-light.yaml) — включение и выключение света в
  спальне голосом. Перед загрузкой в приложение Маруси подставьте `{hass_server}` — адрес вашего
  Home Assistant — и `{long-living-token}` — долгосрочный токен доступа из профиля Home Assistant.
- [`example.yaml`](example.yaml) — пример от разработчиков Маруси: Philips Hue через IFTTT.

Как настроить руками — статья на Хабре:
[Как подружить Марусю и Home Assistant](https://habr.com/ru/articles/649571/).

## Ограничение

DIY-хуки умеют включить, выключить и прочитать состояние (вкл/выкл). Показание датчика
(например, температуру) через них не прочитать.

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
