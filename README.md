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

Replace `index.html` with the newly exported bundle and push. That's the whole deploy.
