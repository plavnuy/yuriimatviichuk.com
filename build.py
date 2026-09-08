#!/usr/bin/env python3
"""Собирает статический сайт yuram.com.ua из tpl/ в docs/ (для GitHub Pages).

Страницы генерируются для каждого языка: /<lang>/ и /<lang>/<page>/.
Галереи собираются из содержимого docs/pix/<каталог>/, подписи к фото —
из tpl/<lang>/<page>.ini. Все пути в HTML относительные, поэтому сайт
одинаково работает и в корне домена, и в подкаталоге user.github.io/repo/.

Оформление живёт в docs/inc/main.css и этим скриптом не перезаписывается.
"""

import hashlib
import html as html_mod
import re
import shutil
import struct
from pathlib import Path

ROOT = Path(__file__).parent
TPL = ROOT / "tpl"
OUT = ROOT / "docs"

LANGS = ["en", "uk", "fr", "nl"]          # первый — базовый; es отключён, как и в исходной версии
PAGES = ["neobarocco", "askoldova", "modern", "renaissance",
         "functionalism", "art", "valera", "ira"]
IMG_EXT = {".jpg", ".jpeg", ".png", ".gif"}
EMAIL = "uuuram@gmail.com"
PHONE = "+38 067 930 31 20"       # как показывать
PHONE_TEL = "+380679303120"       # как звонить
CSS_VERSION = ""            # заполняется в main() хешем файлов оформления
REPO = "yuram.com.ua"          # имя репозитория: нужно странице 404, когда сайт лежит в подкаталоге

SKIP_LINK = {"en": "Skip to content", "uk": "Перейти до вмісту",
             "fr": "Aller au contenu", "nl": "Naar de inhoud"}

# страница -> (показывать текст?, [(каталог с фото, ini с подписями)])
GALLERIES = {
    "neobarocco":    (True,  [("pix/neobarocco", None)]),
    "askoldova":     (True,  [("pix/askoldova", None), ("pix/askoldova/process", None)]),
    "modern":        (True,  [("pix/modern1", None)]),
    "renaissance":   (True,  [("pix/renaissance", None)]),
    "functionalism": (False, [("pix/functionalism1", None)]),
    "art":           (True,  [("pix/art", "art")]),
    "valera":        (False, [("pix/valera", "valera")]),
    "ira":           (False, [("pix/ira", "ira")]),
}

# плитки на главной: страница, фото, ключ подписи в text.ini
TILES = [
    ("neobarocco",    "pix/interior1.jpg", "title1"),
    ("askoldova",     "pix/askoldova.jpg", "title2"),
    ("modern",        "pix/interior2.jpg", "title3"),
    ("renaissance",   "pix/interior3.jpg", "title4"),
    ("functionalism", "pix/interior4.jpg", "title5"),
    ("art",           "pix/etc.jpg",       "title6"),
]


# ---------- чтение исходников ----------

def parse_ini(path):
    """Аналог PHP parse_ini_file: `ключ = значение`, значение может быть
    в кавычках и продолжаться на следующих строках."""
    values = {}
    if not path.is_file():
        return values
    key, buf = None, []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
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
            continue                       # кавычка не закрыта — значение продолжается
        if joined.startswith('"') and joined.endswith('"'):
            joined = joined[1:-1]
        values[key] = joined.strip()
        key, buf = None, []
    return values


def read_content(lang, name):
    f = TPL / lang / f"{name}.html"
    return f.read_text(encoding="utf-8-sig") if f.is_file() else ""


def has_text(fragment):
    return bool(re.sub(r"<[^>]+>", "", fragment).strip())


def list_images(rel_dir):
    """Каталоги с фото лежат внутри docs/ — это и есть корень сайта."""
    d = OUT / rel_dir
    if not d.is_dir():
        return []
    return sorted(f.name for f in d.iterdir()
                  if f.is_file() and f.suffix.lower() in IMG_EXT)


def image_size(path):
    """Размеры JPEG/PNG/GIF без сторонних библиотек — нужны атрибуты width и
    height, иначе страница «прыгает» во время загрузки фото."""
    data = path.read_bytes()
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", data[16:24])
        return w, h
    if data[:6] in (b"GIF87a", b"GIF89a"):
        w, h = struct.unpack("<HH", data[6:10])
        return w, h
    if data[:2] == b"\xff\xd8":                      # JPEG: ищем маркер SOF
        i = 2
        while i < len(data) - 9:
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            length = struct.unpack(">H", data[i + 2:i + 4])[0]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                          0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return w, h
            i += 2 + length
    return None, None


# ---------- подготовка фрагментов ----------

def prepare(fragment, prefix, lang):
    """Готовит текстовый фрагмент из tpl/ к вставке: убирает пустые колонки,
    делает пути относительными, ссылки на страницы — рабочими,
    телефоны — кликабельными на мобильных (callto: давно не работает)."""
    fragment = re.sub(r"<div class='(?:col\d|far col\d)'>\s*(?:<p>\s*</p>\s*)?</div>\s*", "", fragment)
    fragment = fragment.replace("callto:", "tel:")
    fragment = re.sub(r'(src|href)=(["\'])/(pix|img|inc)/',
                      lambda m: f'{m.group(1)}={m.group(2)}{prefix}{m.group(3)}/', fragment)
    fragment = re.sub(r'(href)=(["\'])(' + "|".join(PAGES) + r')\2',
                      lambda m: f'{m.group(1)}={m.group(2)}{prefix}{lang}/{m.group(3)}/{m.group(2)}',
                      fragment)
    return fragment.strip()


def gallery_html(page, lang, prefix, heading):
    _, galleries = GALLERIES[page]
    figures, captioned, shown = [], False, 0
    for rel_dir, ini_name in galleries:
        subs = parse_ini(TPL / lang / f"{ini_name}.ini") if ini_name else {}
        for name in list_images(rel_dir):
            caption = subs.get(name, "")
            captioned = captioned or bool(caption)
            w, h = image_size(OUT / rel_dir / name)
            dims = f' width="{w}" height="{h}"' if w else ""
            shown += 1
            loading = "" if shown <= 2 else ' loading="lazy" decoding="async"'
            figcaption = f"\n\t\t<figcaption>{caption}</figcaption>" if caption else ""
            alt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", caption)).strip() or heading
            figures.append(
                f'\t<figure>\n\t\t<img src="{prefix}{rel_dir}/{name}"'
                f' alt="{html_mod.escape(alt, quote=True)}"{dims}{loading} />'
                f'{figcaption}\n\t</figure>')
    if not figures:
        return ""
    cls = "gallery gallery--captions" if captioned else "gallery"
    return (f'<div class="wrap">\n<div class="{cls}">\n'
            + "\n".join(figures) + "\n</div>\n</div>")


# ---------- сборка страницы ----------

def render(lang, page, prefix):
    txt = parse_ini(TPL / lang / "text.ini")
    page_ini = parse_ini(TPL / lang / f"{page}.ini") if page else {}
    header = page_ini.get("header", "")
    site_title = txt.get("title", "")
    name, _, tagline = site_title.partition(". ")

    bio = prepare(read_content(lang, "bio"), prefix, lang)
    bio = "\n".join("\t\t\t" + line.strip() for line in bio.splitlines() if line.strip())

    body = []
    if page == "":
        body.append(f'<h1 class="visually-hidden">{site_title}</h1>')
        tiles = []
        for slug, img, key in TILES:
            title = txt.get(key, "")
            w, h = image_size(OUT / img)
            dims = f' width="{w}" height="{h}"' if w else ""
            tiles.append(
                f'\t<a class="project" href="{prefix}{lang}/{slug}/">\n'
                f'\t\t<img src="{prefix}{img}" alt=""{dims} />\n'
                f'\t\t<span>{title}</span>\n\t</a>')
        body.append('<div class="wrap">\n<div class="projects">\n'
                    + "\n".join(tiles) + '\n</div>\n</div>')
        doc_title = site_title
    else:
        show_text, _ = GALLERIES[page]
        heading = header
        if heading:
            body.append(f'<div class="wrap page-head">\n\t<h1>{heading}</h1>\n</div>')
        if show_text:
            content = prepare(read_content(lang, page), prefix, lang)
            if has_text(content):
                body.append(f'<div class="wrap">\n<div class="intro">\n{content}\n</div>\n</div>')
        gallery = gallery_html(page, lang, prefix, heading)
        if gallery:
            body.append(gallery)
        doc_title = f"{heading} — {site_title}" if heading else site_title

    current = ' aria-current="true"'
    langs = "\n".join(
        f'\t\t\t<a href="{prefix}{l}/" hreflang="{l}" lang="{l}"'
        + (current if l == lang else "")
        + f'>{l}</a>'
        for l in LANGS)
    alternates = "\n".join(
        f'\t<link rel="alternate" hreflang="{l}" href="{prefix}{l}/{page + "/" if page else ""}" />'
        for l in LANGS)

    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
\t<meta charset="utf-8" />
\t<meta name="viewport" content="width=device-width, initial-scale=1" />
\t<title>{html_mod.escape(doc_title, quote=False)}</title>
\t<meta name="description" content="{html_mod.escape(doc_title, quote=True)}" />
\t<meta property="og:title" content="{html_mod.escape(doc_title, quote=True)}" />
\t<meta property="og:type" content="website" />
\t<meta property="og:image" content="{prefix}pix/interior1.jpg" />
{alternates}
\t<link rel="icon" href="{prefix}img/logo.png" type="image/png" />
\t<link rel="stylesheet" href="{prefix}inc/fonts.css?v={CSS_VERSION}" />
\t<link rel="stylesheet" href="{prefix}inc/main.css?v={CSS_VERSION}" />
</head>
<body>
<a class="skip-link" href="#content">{SKIP_LINK[lang]}</a>
<header class="site-header">
\t<div class="wrap site-header__inner">
\t\t<a class="brand" href="{prefix}{lang}/"><img src="{prefix}img/logo.png" width="237" height="46" alt="{html_mod.escape(name, quote=True)}" /></a>
\t\t<div class="contacts">
\t\t\t<a href="tel:{PHONE_TEL}">{PHONE}</a>
\t\t\t<a href="mailto:{EMAIL}">{EMAIL}</a>
\t\t</div>
\t</div>
</header>
<main id="content">
{chr(10).join(body)}
</main>
<footer class="site-footer">
\t<div class="wrap site-footer__inner">
\t\t<div class="site-footer__bio">
{bio}
\t\t</div>
\t\t<div class="site-footer__meta">
\t\t\t<div class="langs">
{langs}
\t\t\t</div>
\t\t\t<span>© {name}</span>
\t\t</div>
\t</div>
</footer>
</body>
</html>
"""


def render_404():
    """Отдаётся при любом неверном адресе, на любом уровне вложенности, поэтому
    страница полностью самодостаточна: стили внутри, а ссылка на главную
    вычисляется из адреса (сайт может лежать в подкаталоге GitHub Pages)."""
    lang = LANGS[0]
    txt = parse_ini(TPL / lang / "text.ini")
    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
\t<meta charset="utf-8" />
\t<meta name="viewport" content="width=device-width, initial-scale=1" />
\t<title>404 — {txt.get('title', '')}</title>
\t<style>
\t\tbody {{ margin: 0; min-height: 100vh; display: grid; align-content: center;
\t\t\tbackground: #faf9f7; color: #1c1b19; padding: 2rem clamp(1.25rem, 4vw, 3rem);
\t\t\tfont: 400 .9375rem/1.6 'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif; }}
\t\th1 {{ margin: 0 0 .75rem; font-size: clamp(2.25rem, 9vw, 3.5rem); font-weight: 600;
\t\t\tletter-spacing: -.03em; line-height: 1; }}
\t\tp {{ margin: 0; color: #6b675f; }}
\t\ta {{ color: #8c5a3c; }}
\t</style>
</head>
<body>
\t<main>
\t\t<h1>404</h1>
\t\t<p>This page does not exist. <a id="home" href="/">Go to the home page</a>.</p>
\t</main>
\t<script>
\t\t// сайт может обслуживаться из подкаталога вида /{REPO}/ — учитываем это
\t\tvar seg = location.pathname.split('/').filter(Boolean);
\t\tif (seg[0] === '{REPO}') document.getElementById('home').href = '/{REPO}/';
\t</script>
</body>
</html>
"""


def css_version():
    """Короткий хеш от файлов оформления — подставляется в адрес CSS, чтобы
    браузер не показывал старую версию из кэша после правок."""
    h = hashlib.md5()
    for name in ("fonts.css", "main.css"):
        f = OUT / "inc" / name
        if f.is_file():
            h.update(f.read_bytes())
    return h.hexdigest()[:8]


def main():
    global CSS_VERSION
    CSS_VERSION = css_version()

    for name in LANGS + ["ru", "es", "index.html", "404.html"]:
        target = OUT / name
        if target.is_dir():
            shutil.rmtree(target)
        elif target.is_file():
            target.unlink()

    pages = 0
    for lang in LANGS:
        (OUT / lang).mkdir(parents=True, exist_ok=True)
        (OUT / lang / "index.html").write_text(render(lang, "", "../"), encoding="utf-8")
        pages += 1
        for page in PAGES:
            d = OUT / lang / page
            d.mkdir(parents=True, exist_ok=True)
            (d / "index.html").write_text(render(lang, page, "../../"), encoding="utf-8")
            pages += 1

    default = LANGS[0]
    (OUT / "index.html").write_text(f"""<!DOCTYPE html>
<html lang="{default}">
<head>
\t<meta charset="utf-8" />
\t<meta http-equiv="refresh" content="0; url={default}/" />
\t<link rel="canonical" href="{default}/" />
\t<title>Yuriy Matviychuk. Artist. Designer.</title>
</head>
<body><p><a href="{default}/">yuram.com.ua</a></p></body>
</html>
""", encoding="utf-8")
    (OUT / "404.html").write_text(render_404(), encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    print(f"собрано: {pages} страниц ({', '.join(LANGS)}) + index.html + 404.html")


if __name__ == "__main__":
    main()
