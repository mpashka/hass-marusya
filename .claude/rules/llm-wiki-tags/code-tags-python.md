---
description: "Куда ставить токены @tag: в Python-коде."
paths: ["**/*.py"]
---

# llm-wiki-tags — тэги в Python

Токен `@tag:<slug>` ставится в `#`-комментарии прямо над элементом либо внутри
его docstring. Несколько тэгов — через пробел. Формат и реестр:
[`tags.md`](tags.md).

- **Пакет** — в `__init__.py` пакета: комментарий вверху файла или docstring
  модуля:
  ```python
  # @tag:payments
  ```
- **Модуль / файл** — `#`-комментарий вверху `.py`-файла (ниже импортов
  `from __future__`) или docstring модуля:
  ```python
  """Payments domain. @tag:payments"""
  ```
- **Класс** — комментарий прямо над `class` или его docstring:
  ```python
  # @tag:payments
  class ChargeService:
      """Charges a card. @tag:payments/retry"""
  ```
- **Функция / метод** — комментарий прямо над `def` или его docstring:
  ```python
  # @tag:payments/retry
  def charge(card): ...
  ```
