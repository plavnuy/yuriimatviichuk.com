#!/usr/bin/env python3
"""Собирает статическую версию yuram.com.ua из tpl/ в docs/ (для GitHub Pages).

Повторяет логику старого PHP (pages.php + tpl/*.php):
  - страницы для каждого языка: /<lang>/ и /<lang>/<page>/
  - галереи собираются из содержимого pix/<dir>/
  - подписи к картинкам берутся из tpl/<lang>/<page>.ini
Все пути в HTML/CSS делаются относительными, чтобы сайт работал
и в корне домена, и в подкаталоге (user.github.io/repo/).
"""

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).parent
TPL = ROOT / "tpl"
OUT = ROOT / "docs"

LANGS = ["ru", "uk", "fr", "nl"]          # es отключён так же, как в старом header.php
PAGES = ["neobarocco", "askoldova", "modern", "renaissance",
         "functionalism", "art", "valera", "ira", "contact"]
IMG_EXT = {".jpg", ".jpeg", ".png", ".gif"}

# страница -> (показывать текст?, [(каталог картинок, ini-файл с подписями)])
GALLERIES = {
    "neobarocco":    (True,  [("pix/neobarocco", None)]),
    "askoldova":     (True,  [("pix/askoldova", None), ("pix/askoldova/process", None)]),
    "modern":        (True,  [("pix/modern1", None)]),
    "renaissance":   (True,  [("pix/renaissance", None)]),
    "functionalism": (False, [("pix/functionalism1", None)]),
    "art":           (True,  [("pix/art", "art")]),
    "valera":        (False, [("pix/valera", "valera")]),
    "ira":           (False, [("pix/ira", "ira")]),
    "contact":       (True,  []),
}


def parse_ini(path):
    """Аналог PHP parse_ini_file: key = value, значения могут быть в кавычках
    и продолжаться на следующих строках."""
    values = {}
    if not path.is_file():
        return values
    text = path.read_text(encoding="utf-8-sig")
    key, buf = None, []
    for line in text.splitlines():
        if key is None:
            stripped = line.strip()
            if not stripped or stripped.startswith((";", "#")) or "=" not in stripped:
                continue
            k, _, v = stripped.partition("=")
            key, buf = k.strip(), [v.strip()]
        else:
            buf.append(line.strip())
        joined = "\n".join(buf).strip()
        if joined.startswith('"') and not (joined.endswith('"') and len(joined) > 1):
            continue                      # незакрытая кавычка — значение продолжается
        if joined.startswith('"') and joined.endswith('"'):
            joined = joined[1:-1]
        values[key] = joined.strip()
        key, buf = None, []
    return values


def list_images(rel_dir):
    """Каталоги с картинками живут внутри docs/ (это и есть корень сайта)."""
    d = OUT / rel_dir
    if not d.is_dir():
        return []
    return sorted(f.name for f in d.iterdir()
                  if f.is_file() and f.suffix.lower() in IMG_EXT)


def localize(html, prefix, lang):
    """Абсолютные /pix, /img -> относительные; ссылки на страницы -> /<lang>/<page>/."""
    html = re.sub(r'(src|href)=(["\'])/(pix|img|inc)/',
                  lambda m: f'{m.group(1)}={m.group(2)}{prefix}{m.group(3)}/', html)
    def page_link(m):
        target = m.group(3)
        return f'{m.group(1)}={m.group(2)}{prefix}{lang}/{target}/{m.group(2)}'
    html = re.sub(r'(href)=(["\'])(' + "|".join(PAGES) + r')\2', page_link, html)
    return html


def read_content(lang, name):
    f = TPL / lang / f"{name}.html"
    if not f.is_file():
        return ""
    return f.read_text(encoding="utf-8-sig")


def render(lang, page, prefix):
    txt = parse_ini(TPL / lang / "text.ini")
    page_ini = parse_ini(TPL / lang / f"{page}.ini") if page else {}
    header = page_ini.get("header", "")

    rows = []

    if page == "":
        # мозаика из шести проектов + вступительный текст (бывший index.php)
        tiles = [
            ("neobarocco",    "pix/interior1.jpg", txt.get("title1", "")),
            ("askoldova",     "pix/askoldova.jpg", txt.get("title2", "")),
            ("modern",        "pix/interior2.jpg", txt.get("title3", "")),
            ("renaissance",   "pix/interior3.jpg", txt.get("title4", "")),
            ("functionalism", "pix/interior4.jpg", txt.get("title5", "")),
            ("art",           "pix/etc.jpg",       txt.get("title6", "")),
        ]
        cells = []
        for slug, img, title in tiles:
            cells.append(
                f"\t\t<td><a href='{prefix}{lang}/{slug}/'>"
                f"<img width=\"300\" src='{prefix}{img}' alt='{title}' /><br/>{title}</a></td>")
        mosaic = ("\t<table class='mosaic'>\n\t<tr>\n"
                  + "\n".join(cells[:3]) + "\n\t</tr>\n\t<tr>\n"
                  + "\n".join(cells[3:]) + "\n\t</tr>\n\t</table>")
        rows.append(f"<tr>\n<td class='main_image'>\n{mosaic}\n</td>\n"
                    f"<td class='main_text'>\n\t<div class='text'>\n"
                    f"\t\t<p>{txt.get('index_text', '')}</p>\n\t</div>\n</td>\n</tr>")
        rows.append("<tr>\n<td class='block_text'>\n"
                    + localize(read_content(lang, "index"), prefix, lang)
                    + "\n</td>\n<td class='list_text'></td>\n</tr>")
    else:
        show_text, galleries = GALLERIES[page]
        if page != "contact":
            rows.append(f"<tr>\n<td class='main_image'><h2>{header}</h2></td>\n<td></td>\n</tr>")
        if show_text:
            rows.append("<tr>\n<td class='block_text'>\n"
                        + localize(read_content(lang, page), prefix, lang)
                        + "\n</td>\n<td class='list_text'></td>\n</tr>")
        counter = 0
        for rel_dir, ini_name in galleries:
            subs = parse_ini(TPL / lang / f"{ini_name}.ini") if ini_name else {}
            images = list_images(rel_dir)
            for name in images:
                counter += 1
                caption = subs.get(name, "")
                rows.append(
                    f"<tr>\n\t<td class='list_image'>\n"
                    f"\t\t<a id='image{counter}' name='image{counter}' href='#image{counter + 1}'>\n"
                    f"\t\t\t<img src='{prefix}{rel_dir}/{name}' alt='' />\n\t\t</a>\n\t</td>\n"
                    f"\t<td class='list_text'>{caption}</td>\n</tr>")

    title = f"{header} {txt.get('title', '')}".strip()
    lang_links = " ".join(f"<a href='{prefix}{l}/'>{l}</a>" for l in LANGS)
    menu = (
        f"<a href=\"{prefix}{lang}/\"{' class=\"current\"' if page == '' else ''}>"
        f"{txt.get('projects', '')}</a><br/>\n"
        f"\t\t\t<a href=\"{prefix}{lang}/contact/\""
        f"{' class=\"current\"' if page == 'contact' else ''}>{txt.get('contacts', '')}</a>"
    )

    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
\t<meta charset="utf-8" />
\t<title>{title}</title>
\t<meta name="viewport" content="width=device-width, initial-scale=1" />
\t<meta name="description" content="{txt.get('title', '')}" />
\t<link rel="stylesheet" href="{prefix}inc/main.css" type="text/css" />
</head>
<body>
<div class="superheader">
\t<div class='lang'>{lang_links}</div>
</div>
<div id="ALL">
\t<div class="header">
\t\t<a class='logo' href='{prefix}{lang}/'><img src='{prefix}img/logo.png' alt='' /></a>
\t\t<div class='menu'>
\t\t\t{menu}
\t\t</div>
\t</div>

\t<table class='main'>
{chr(10).join(rows)}
\t</table>
\t<div class="footer"></div>
</div>
</body>
</html>
"""


def main():
    for name in ("ru", "uk", "fr", "nl", "index.html", "404.html"):
        target = OUT / name
        if target.is_dir():
            shutil.rmtree(target)
        elif target.is_file():
            target.unlink()

    written = 0
    for lang in LANGS:
        (OUT / lang).mkdir(parents=True, exist_ok=True)
        (OUT / lang / "index.html").write_text(render(lang, "", "../"), encoding="utf-8")
        written += 1
        for page in PAGES:
            d = OUT / lang / page
            d.mkdir(parents=True, exist_ok=True)
            (d / "index.html").write_text(render(lang, page, "../../"), encoding="utf-8")
            written += 1

    default = LANGS[0]
    (OUT / "index.html").write_text(
        f"""<!DOCTYPE html>
<html lang="{default}">
<head>
\t<meta charset="utf-8" />
\t<meta http-equiv="refresh" content="0; url={default}/" />
\t<link rel="canonical" href="{default}/" />
\t<title>Юрий Матвийчук. Художник. Дизайнер.</title>
</head>
<body><p><a href="{default}/">yuram.com.ua</a></p></body>
</html>
""", encoding="utf-8")

    (OUT / "404.html").write_text(
        """<!DOCTYPE html>
<html lang="ru">
<head>
\t<meta charset="utf-8" />
\t<title>404. Not found</title>
\t<meta name="viewport" content="width=device-width, initial-scale=1" />
\t<style>body{font:normal 12px sans-serif;color:#555;background:#eee;text-align:center;padding:15% 1em}h1{font:normal 40px serif}a{color:#666}</style>
</head>
<body>
\t<h1>404. Not found</h1>
\t<p><a href="/">yuram.com.ua</a></p>
</body>
</html>
""", encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")

    print(f"docs/: {written} страниц + index.html + 404.html")


if __name__ == "__main__":
    main()
