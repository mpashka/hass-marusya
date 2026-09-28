"""Synthetic cabinet pages with the markup of the real ones and no personal data."""

CSRF = "0123456789abcdef0123456789abcdef"


def _item(name: str, date: str, link: str) -> str:
    return f"""
              <div class="all-sk__item">
                <div class="all-sk__item-img"><img src="x.png"></div>
                <div class="all-sk__item-body">
                  <div class="all-sk__item-name">{name}</div>
                  <div class="all-sk__item-desc">
                    {date}
                    <div class="all-sk__item-commands">
                        <div class="sk__command"> Свет </div>
                      <br />
                      {link}
                    </div>
                  </div>
                </div>
              </div>"""


def cabinet_page(configs: list[tuple[str, str]], csrf: str = CSRF) -> str:
    items = "".join(
        _item(name, "2026-09-28 10:00", f'<a href="?remove={cid}" class="sk__command show--all">Удалить</a>')
        for cid, name in configs
    )
    return f"""<html><body>
      <div class="all-sk__item"><div class="all-sk__item-name"> Загрузка описания </div>
      <div class="all-sk__item-desc">Загрузите файл</div></div>
      <form method="POST" enctype="multipart/form-data">
        <input type="hidden" name="_csrf_token" value="{csrf}" />
        <input name="upload" type="file" /><textarea name="yaml"></textarea>
      </form>{items}
      <div class="all-sk__item"><div class="all-sk__item-name">Пример описания в формате YAML</div>
      <div class="all-sk__item-desc">- id: lamp</div></div>
    </body></html>"""


def choice_page(configs: list[tuple[str, str]]) -> str:
    items = "".join(
        _item(name, "2026-09-28 10:00",
              f'<a href="?select={cid}" data-link="{cid}" class="sk__command show--all">Выбрать</a>')
        for cid, name in configs
    )
    return f"""<html><body>
      <div class="all-sk__item"><div class="all-sk__item-name"> Авторизация </div>
      <div class="all-sk__item-desc">Выберите описание</div></div>{items}
      <form method="POST" id="form"><input type="hidden" name="house" id="house" value="" /></form>
    </body></html>"""
