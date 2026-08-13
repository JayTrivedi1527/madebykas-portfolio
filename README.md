# made by kas

Portfolio site for **made by kas** — Kasvi's product design, packaging, and visual identity work.

## What's here

- `index.html` — the entire site. It's a self-contained bundle: images (webp), fonts, and JS are embedded in the file and unpacked in the browser on load. No build step, no dependencies.
- `.nojekyll` — tells GitHub Pages to serve the files as-is.

## Running it locally

Open `index.html` in a browser, or serve the folder:

```bash
python3 -m http.server 8000
```

Then visit http://localhost:8000

## Updating the site

`scripts/patch-export.py` fixes four things the design tool can't emit, and
none of them are in Kasvi's source — so **every new export must be run through
it**:

- **History** — Back used to leave the site entirely. Each view now gets a
  history entry, which also makes pages deep-linkable (`#/about`, `#/products`,
  `#/project/arc-lamp`).
- **Metadata** — adds the title, description, favicon and Open Graph tags the
  export omits, so tabs are named and shared links preview properly.
- **Links** — repoints the social links at the real profiles and the footer
  email at an address that can actually receive mail.
- **Nav** — strips the stray `&nbsp;` from the Archive label.

Run it on each new export:

```bash
cp ~/Downloads/NEW.html src-export.html
python3 scripts/patch-export.py src-export.html index.html
git commit -am "Update site" && git push
```

`src-export.html` is the unmodified export, kept so the patch can always be
re-derived. `index.html` is the patched file that actually ships. Pushing to
`main` deploys automatically.

If a future export renames its navigation methods, the script exits with an
error rather than shipping an unpatched page — update the replacements in
`scripts/patch-export.py` when that happens.
