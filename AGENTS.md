# AGENTS.md — `hass-marusya`: колонка «Маруся» и Home Assistant через DIY Hooks

Интеграция Home Assistant `marusya_diy` (ставится через HACS): вход в аккаунты Маруси, загрузка
конфигурации DIY в кабинет и привязка к аккаунту — без мобильного приложения.

- Система вокруг и контракты сервера Маруси — [`docs/external/`](docs/external/index.md).
- Что интеграция обещает — [`docs/specification/`](docs/specification/index.md).
- Как устроена — [`docs/implementation/`](docs/implementation/index.md).
- Задачи — `docs/requests/<задача>/` (`request.md` + `plan.md`), вне git.

## llm-wiki-tags

Документация — llm-wiki: `index.md` в каждом значимом каталоге, один факт — одна страница,
раскладка `docs/external|specification|implementation|testing`. Сквозные понятия связаны тегами
`@tag:<slug>` в коде, документации и диаграммах — реестр [`docs/tags.md`](docs/tags.md), словарь
[`docs/terms.md`](docs/terms.md). Правила — `.claude/rules/llm-wiki-tags/`.

## Границы

- 🚨 **Репозиторий публичный** (`github.com/mpashka/hass-marusya`): ни личных id VK, ни адресов
  чьего-то Home Assistant, ни сессий и токенов — ни в коде, ни в образцах страниц для тестов.
- Протокол Маруси неофициальный: каждое утверждение о сервере в `docs/external/` либо проверено
  живьём, либо помечено «не проверено».
- Язык документации — русский, имена в коде — английские.
- Устройство меняется — тем же изменением правятся диаграммы `.puml`; проверка синтаксиса —
  `plantuml -checkonly docs/**/*.puml`.
