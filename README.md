# yuriimatviichuk.com

Portfolio of Yurii Matviichuk — monumental painting, murals, stained glass and
interior design. Published with GitHub Pages from `docs/`.

## Layout

```
tpl/         texts and captions per language (en, uk, fr, nl) — edit here
docs/pix/    photographs; galleries are built from these folders
docs/inc/    stylesheet
docs/img/    logotype and favicons (monogram.png is the master image)
build.py     generator: tpl/ + docs/pix/ -> HTML in docs/
legacy-php/  the original 2015 PHP version, kept for reference
```

## Editing

Text lives in `tpl/<lang>/<page>.html`; headings and project names in
`tpl/<lang>/text.ini` and `tpl/<lang>/<page>.ini`.

To add a photograph, drop it into the right `docs/pix/<project>/` folder.
Galleries are ordered by file name, so numbered names work best
(`001.jpg`, `002.jpg`). An optional caption goes into
`tpl/<lang>/<page>.ini` as `001.jpg = "oil on canvas (400×300)"`.

Then rebuild and publish:

```sh
python3 build.py
git add -A && git commit -m "what changed" && git push
```

The site updates a minute or two later.

## Preview locally

```sh
python3 build.py
python3 -m http.server -d docs 8000    # http://localhost:8000
```
