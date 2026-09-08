#!/usr/bin/env python3
"""Builds the static site from tpl/ into docs/ for GitHub Pages.

One set of pages per language: /<lang>/ and /<lang>/<page>/. Galleries are
built from whatever sits in docs/pix/<folder>/; captions come from
tpl/<lang>/<page>.ini. Every path in the HTML is relative, so the site works
both at a domain root and in a subdirectory such as user.github.io/repo/.

Styling lives in docs/inc/main.css and is never overwritten by this script.
"""

import hashlib
import html as html_mod
import json
import re
import shutil
import struct
from pathlib import Path

ROOT = Path(__file__).parent
TPL = ROOT / "tpl"
OUT = ROOT / "docs"

LANGS = ["en", "uk", "fr", "nl"]          # first one is the default; es exists in tpl/ but is off
PAGES = ["neo-baroque", "askold-church", "art-nouveau", "renaissance",
         "functionalism", "works", "valeriy-vasiliev", "iryna-ganina"]

# old 2015 addresses -> current ones; redirect stubs are generated for the old
# paths so that links saved anywhere out there keep working
OLD_PAGES = {
    "neobarocco": "neo-baroque",
    "askoldova": "askold-church",
    "modern": "art-nouveau",
    "art": "works",
    "valera": "valeriy-vasiliev",
    "ira": "iryna-ganina",
    "renaissance": "renaissance",
    "functionalism": "functionalism",
    "contact": "",                 # the contacts page is gone; send it to the home page
}
OLD_LANGS = ["ru", "uk", "fr", "nl", "es", "en"]
IMG_EXT = {".jpg", ".jpeg", ".png", ".gif"}
EMAIL = "uuuram@gmail.com"
PHONE = "+38 067 930 31 20"       # as displayed
PHONE_TEL = "+380679303120"       # as dialled
CSS_VERSION = ""            # filled in main() with a hash of the stylesheets
DOMAIN = "yuriimatviichuk.com"     # custom domain, written to docs/CNAME
REPO = "yuriimatviichuk.com"          # repository name; the 404 page needs it in a subdirectory

SUBSET = {"uk": "cyrillic"}      # which font subset to preload
BASE = f"https://{DOMAIN}"       # absolute URLs are required by canonical, hreflang and Open Graph

OG_LOCALE = {"en": "en_GB", "uk": "uk_UA", "fr": "fr_FR", "nl": "nl_NL"}

# these two pages show the work of colleagues, not of Yurii
PAGE_AUTHOR = {"valeriy-vasiliev": "Valeriy Vasiliev", "iryna-ganina": "Iryna Ganina"}

# used as a description when a page carries no text of its own
DESC_FALLBACK = {
    "en": "{heading} — work by {name}, monumental painter and interior designer.",
    "uk": "{heading} — роботи {name}, монументальний живопис та дизайн інтер'єрів.",
    "fr": "{heading} — travaux de {name}, peinture monumentale et design d'intérieur.",
    "nl": "{heading} — werk van {name}, monumentale schilderkunst en interieurontwerp.",
}

# the same, for the pages of colleagues
DESC_FALLBACK_OTHER = {
    "en": "{heading} — photographs of the work.",
    "uk": "{heading} — фотографії робіт.",
    "fr": "{heading} — photographies des travaux.",
    "nl": "{heading} — foto's van het werk.",
}

SKIP_LINK = {"en": "Skip to content", "uk": "Перейти до вмісту",
             "fr": "Aller au contenu", "nl": "Naar de inhoud"}

# page -> (show its text?, [(photo folder, ini file holding captions)])
GALLERIES = {
    "neo-baroque":      (True,  [("pix/neobarocco", None)]),
    "askold-church":    (True,  [("pix/askoldova", None), ("pix/askoldova/process", None)]),
    "art-nouveau":      (True,  [("pix/modern1", None)]),
    "renaissance":      (True,  [("pix/renaissance", None)]),
    "functionalism":    (False, [("pix/functionalism1", None)]),
    "works":            (True,  [("pix/art", "works")]),
    "valeriy-vasiliev": (False, [("pix/valera", "valeriy-vasiliev")]),
    "iryna-ganina":     (False, [("pix/ira", "iryna-ganina")]),
}

# home page tiles: page, photo, caption key in text.ini
TILES = [
    ("neo-baroque",   "pix/interior1.jpg", "title1"),
    ("askold-church", "pix/askoldova.jpg", "title2"),
    ("art-nouveau",   "pix/interior2.jpg", "title3"),
    ("renaissance",   "pix/interior3.jpg", "title4"),
    ("functionalism", "pix/interior4.jpg", "title5"),
    ("works",         "pix/etc.jpg",       "title6"),
]


# ---------- reading the sources ----------

def parse_ini(path):
    """Same shape as PHP parse_ini_file: `key = value`, where a value may be
    quoted and may continue on the following lines."""
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
            continue                       # quote still open: the value continues
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
    """Photo folders live inside docs/, which is the site root."""
    d = OUT / rel_dir
    if not d.is_dir():
        return []
    return sorted(f.name for f in d.iterdir()
                  if f.is_file() and f.suffix.lower() in IMG_EXT)


def image_size(path):
    """JPEG/PNG/GIF dimensions without any third-party library: width and
    height attributes keep the page from jumping while photos load."""
    data = path.read_bytes()
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", data[16:24])
        return w, h
    if data[:6] in (b"GIF87a", b"GIF89a"):
        w, h = struct.unpack("<HH", data[6:10])
        return w, h
    if data[:2] == b"\xff\xd8":                      # JPEG: look for the SOF marker
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


# ---------- preparing fragments ----------

def prepare(fragment, prefix, lang):
    """Gets a fragment from tpl/ ready to embed: drops empty columns, makes
    paths relative, fixes links between pages, and turns phone numbers into
    tel: links (callto: stopped working years ago)."""
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


def plain_text(fragment, limit=158):
    """Strips a fragment down to plain text for a meta description."""
    t = html_mod.unescape(re.sub(r"<[^>]+>", " ", fragment))
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) <= limit:
        return t
    return t[:limit].rsplit(" ", 1)[0].rstrip(" ,.;:—-") + "…"


def page_url(lang, page):
    """Absolute address of a page."""
    return f"{BASE}/{lang}/" + (f"{page}/" if page else "")


def first_photo(page):
    """First photograph of a page — used as the Open Graph image."""
    if page in GALLERIES:
        for rel_dir, _ in GALLERIES[page][1]:
            images = list_images(rel_dir)
            if images:
                return f"{rel_dir}/{images[0]}"
    return "pix/interior1.jpg"


# ---------- assembling a page ----------

def render(lang, page, prefix):
    txt = parse_ini(TPL / lang / "text.ini")
    page_ini = parse_ini(TPL / lang / f"{page}.ini") if page else {}
    header = page_ini.get("header", "")
    site_title = txt.get("title", "")
    name, _, tagline = site_title.partition(". ")

    subset = SUBSET.get(lang, "latin")
    bio = prepare(read_content(lang, "bio"), prefix, lang)
    bio = "\n".join("\t\t\t" + line.strip() for line in bio.splitlines() if line.strip())

    main_class = ' class="main--home"' if page == "" else ""

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
        description = plain_text(read_content(lang, "bio")) or site_title
        og_photo = "pix/art/001.jpg"     # 800×406 — под пропорции соцсетей
        schema = {
            "@context": "https://schema.org",
            "@graph": [
                {"@type": "WebSite", "@id": f"{BASE}/#website", "url": f"{BASE}/",
                 "name": site_title, "inLanguage": lang,
                 "publisher": {"@id": f"{BASE}/#person"}},
                {"@type": "Person", "@id": f"{BASE}/#person", "name": name,
                 "jobTitle": tagline.rstrip(".").replace(". ", ", "), "url": page_url(lang, ""),
                 "email": f"mailto:{EMAIL}", "telephone": PHONE_TEL,
                 "description": description,
                 "image": f"{BASE}/pix/ava-yura.jpg"},
            ],
        }
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
        doc_title = f"{heading} — {name}" if heading else site_title
        page_text = read_content(lang, page) if show_text else ""
        author = PAGE_AUTHOR.get(page)
        fallback = DESC_FALLBACK_OTHER if author else DESC_FALLBACK
        description = plain_text(page_text) or fallback[lang].format(
            heading=heading, name=name)
        og_photo = first_photo(page)
        gallery_images = [f"{BASE}/{rel}/{img}"
                          for rel, _ in GALLERIES[page][1]
                          for img in list_images(rel)]
        schema = {
            "@context": "https://schema.org",
            "@type": "ImageGallery",
            "name": heading,
            "description": description,
            "url": page_url(lang, page),
            "inLanguage": lang,
            "isPartOf": {"@id": f"{BASE}/#website"},
            "author": ({"@type": "Person", "name": author} if author
                       else {"@id": f"{BASE}/#person"}),
            "image": gallery_images[:12],
        }

    current = ' aria-current="true"'
    langs = "\n".join(
        f'\t\t\t<a href="{prefix}{l}/" hreflang="{l}" lang="{l}"'
        + (current if l == lang else "")
        + f'>{l}</a>'
        for l in LANGS)
    alternates = "\n".join(
        f'\t<link rel="alternate" hreflang="{l}" href="{page_url(l, page)}" />'
        for l in LANGS)
    alternates += f'\n\t<link rel="alternate" hreflang="x-default" href="{page_url(LANGS[0], page)}" />'
    og_alt_locales = "\n".join(
        f'\t<meta property="og:locale:alternate" content="{OG_LOCALE[l]}" />'
        for l in LANGS if l != lang)
    page_author = PAGE_AUTHOR.get(page, name)
    og_w, og_h = image_size(OUT / og_photo)
    ld_json = json.dumps(schema, ensure_ascii=False, indent=1).replace("</", "<\\/")
    esc = lambda t: html_mod.escape(t, quote=True)

    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
\t<meta charset="utf-8" />
\t<meta name="viewport" content="width=device-width, initial-scale=1" />
\t<title>{esc(doc_title)}</title>
\t<meta name="description" content="{esc(description)}" />
\t<meta name="author" content="{esc(page_author)}" />
\t<link rel="canonical" href="{page_url(lang, page)}" />
{alternates}

\t<meta property="og:site_name" content="{esc(name)}" />
\t<meta property="og:type" content="website" />
\t<meta property="og:title" content="{esc(doc_title)}" />
\t<meta property="og:description" content="{esc(description)}" />
\t<meta property="og:url" content="{page_url(lang, page)}" />
\t<meta property="og:locale" content="{OG_LOCALE[lang]}" />
{og_alt_locales}
\t<meta property="og:image" content="{BASE}/{og_photo}" />
\t<meta property="og:image:width" content="{og_w}" />
\t<meta property="og:image:height" content="{og_h}" />
\t<meta property="og:image:alt" content="{esc(doc_title)}" />
\t<meta name="twitter:card" content="summary_large_image" />

\t<script type="application/ld+json">
{ld_json}
\t</script>
\t<link rel="icon" href="{prefix}favicon.ico" sizes="any" />
\t<link rel="icon" href="{prefix}img/favicon-32.png" type="image/png" sizes="32x32" />
\t<link rel="icon" href="{prefix}img/favicon-16.png" type="image/png" sizes="16x16" />
\t<link rel="apple-touch-icon" href="{prefix}img/apple-touch-icon.png" />
\t<link rel="preload" href="{prefix}fonts/inter-400-normal-{subset}.woff2" as="font" type="font/woff2" crossorigin />
\t<link rel="preload" href="{prefix}fonts/inter-600-normal-{subset}.woff2" as="font" type="font/woff2" crossorigin />
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
<main id="content"{main_class}>
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
\t\t</div>
\t</div>
</footer>
</body>
</html>
"""


def render_404():
    """Served for any wrong address, at any depth, so the page is entirely
    self-contained: styles inline, and the link home is derived from the
    current path (the site may live in a GitHub Pages subdirectory)."""
    lang = LANGS[0]
    txt = parse_ini(TPL / lang / "text.ini")
    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
\t<meta charset="utf-8" />
\t<meta name="viewport" content="width=device-width, initial-scale=1" />
\t<title>404 — {txt.get('title', '')}</title>
\t<meta name="robots" content="noindex" />
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
\t\t// the site may be served from a /{REPO}/ subdirectory
\t\tvar seg = location.pathname.split('/').filter(Boolean);
\t\tif (seg[0] === '{REPO}') document.getElementById('home').href = '/{REPO}/';
\t</script>
</body>
</html>
"""


def css_version():
    """Short hash of the stylesheets, appended to their URLs so a browser
    cannot serve a stale copy after they change."""
    h = hashlib.md5()
    for name in ("fonts.css", "main.css"):
        f = OUT / "inc" / name
        if f.is_file():
            h.update(f.read_bytes())
    return h.hexdigest()[:8]


def redirect_page(target, title="Yurii Matviichuk"):
    """A tiny redirect page standing in for an old address."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
\t<meta charset="utf-8" />
\t<meta http-equiv="refresh" content="0; url={target}" />
\t<link rel="canonical" href="{target}" />
\t<meta name="robots" content="noindex" />
\t<title>{title}</title>
</head>
<body><p><a href="{target}">{title}</a></p></body>
</html>
"""


def write_old_url_redirects():
    """Point the old 2015 addresses at their current pages so that links
    saved anywhere out there do not land on a 404."""
    default = LANGS[0]
    made = 0
    for old, new in OLD_PAGES.items():
        d = OUT / old                      # /neobarocco/ -> /en/neo-baroque/
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            target = f"../{default}/" + (f"{new}/" if new else "")
            (d / "index.html").write_text(redirect_page(target), encoding="utf-8")
            made += 1
    for lang in OLD_LANGS:
        target_lang = lang if lang in LANGS else default
        if lang not in LANGS:              # /ru/ -> /en/
            d = OUT / lang
            d.mkdir(parents=True, exist_ok=True)
            (d / "index.html").write_text(redirect_page(f"../{target_lang}/"), encoding="utf-8")
            made += 1
        for old, new in OLD_PAGES.items():
            d = OUT / lang / old
            if d.exists():                 # a real page already occupies this address
                continue
            d.mkdir(parents=True, exist_ok=True)
            target = f"../../{target_lang}/" + (f"{new}/" if new else "")
            (d / "index.html").write_text(redirect_page(target), encoding="utf-8")
            made += 1
    return made


def write_sitemap():
    """Sitemap listing every page in every language, with the language
    alternates spelled out for each address."""
    urls = []
    for lang in LANGS:
        for page in [""] + PAGES:
            alts = "\n".join(
                f'\t\t<xhtml:link rel="alternate" hreflang="{l}" href="{page_url(l, page)}" />'
                for l in LANGS)
            alts += (f'\n\t\t<xhtml:link rel="alternate" hreflang="x-default"'
                     f' href="{page_url(LANGS[0], page)}" />')
            urls.append(f'\t<url>\n\t\t<loc>{page_url(lang, page)}</loc>\n{alts}\n\t</url>')
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
        '        xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
        + "\n".join(urls) + "\n</urlset>\n", encoding="utf-8")
    (OUT / "robots.txt").write_text(
        "User-agent: *\nAllow: /\n\n"
        f"Sitemap: {BASE}/sitemap.xml\n", encoding="utf-8")
    return len(urls)


def main():
    global CSS_VERSION
    CSS_VERSION = css_version()

    for name in LANGS + OLD_LANGS + list(OLD_PAGES) + ["index.html", "404.html"]:
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
\t<link rel="canonical" href="{BASE}/{default}/" />
\t<title>Yurii Matviichuk. Artist. Designer.</title>
\t<meta name="description" content="Monumental painting, murals, stained glass and interior design by Yurii Matviichuk." />
\t<meta property="og:title" content="Yurii Matviichuk. Artist. Designer." />
\t<meta property="og:type" content="website" />
\t<meta property="og:url" content="{BASE}/{default}/" />
\t<meta property="og:image" content="{BASE}/pix/interior1.jpg" />
</head>
<body><p><a href="{default}/">yuram.com.ua</a></p></body>
</html>
""", encoding="utf-8")
    (OUT / "404.html").write_text(render_404(), encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    (OUT / "CNAME").write_text(DOMAIN + "\n", encoding="utf-8")
    redirects = write_old_url_redirects()
    listed = write_sitemap()
    print(f"built: {pages} pages ({', '.join(LANGS)}) + index.html + 404.html"
          f" + {redirects} redirects from old addresses;"
          f" sitemap.xml lists {listed} addresses")


if __name__ == "__main__":
    main()
