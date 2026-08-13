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

The export navigates by internal state, so the browser's Back button would leave
the site entirely. `scripts/patch-history.py` fixes that by giving each view its
own history entry, which also makes sections and projects deep-linkable
(`#/about`, `#/products`, `#/project/arc-lamp`).

That patch is **not** in Kasvi's source, so every new export has to be run
through it:

```bash
cp ~/Downloads/NEW.html src-export.html
python3 scripts/patch-history.py src-export.html index.html
git commit -am "Update site" && git push
```

`src-export.html` is the unmodified export, kept so the patch can always be
re-derived. `index.html` is the patched file that actually ships. Pushing to
`main` deploys automatically.

If a future export renames its navigation methods, the script exits with an
error rather than shipping an unpatched page — update the replacements in
`scripts/patch-history.py` when that happens.
