#!/usr/bin/env python3
"""Patch an exported bundle into the file that actually ships.

The design tool's export has a few gaps that can't be fixed in the tool, so
they're re-applied here on every export:

  history   browser Back left the site entirely — the export navigates by
            React state and never touches the History API. Each view now gets
            a history entry, which also makes sections and projects
            deep-linkable (#/about, #/products, #/project/arc-lamp).
  metadata  the export ships no <title>, description, social tags or favicon,
            so tabs were blank and shared links previewed as nothing.
  links     both social links pointed at instagram.com / linkedin.com rather
            than her profiles, and the footer email was an address the domain
            can't receive mail on.
  slots     moving between projects (Next/Prev) blanked every gallery image:
            the image-slot component only reads its picture on mount, so
            reusing the elements with a new id left them empty. Remounted.
  layout    Archive section removed; home cards go two per row; project
            galleries stack one image per row, uncropped.
  mobile    the export is desktop-only: the nav wrapped into crowded rows and
            the hero wasted most of the first screen. Adds a mobile stylesheet.
  wordmark  "made by kas" appeared twice on the home page (nav + hero), so the
            nav copy now fades in only once the hero has scrolled away.
  copy      a hard <br> in the hero orphaned "to last." onto its own line, and
            two project titles disagreed with their cards.

Usage:

    python3 scripts/patch-export.py src-export.html index.html

Every replacement is asserted. If a future export changes shape, this exits
with an error instead of quietly shipping an unpatched page.
"""
import json
import re
import sys

MARK = "/* history-nav: added post-export */"

SITE_URL = "https://madebykas.com"
# No ampersand: this goes into HTML attributes (og:title, twitter:title) where
# a bare & is invalid and some preview scrapers render it as "&amp;".
SITE_TITLE = "made by kas — product and packaging design by Kasvi"
SITE_DESC = (
    "Product, packaging and brand design by Kasvi. Playful by nature, "
    "practical by design — child-friendly products, purposeful packaging "
    "and visual identity."
)
# Inline SVG so it needs no extra request and can't 404.
FAVICON = (
    "data:image/svg+xml,"
    "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E"
    "%3Crect width='64' height='64' rx='14' fill='%23F1EAE0'/%3E"
    "%3Ctext x='32' y='45' font-family='Helvetica,Arial,sans-serif' "
    "font-size='38' fill='%231A1817' text-anchor='middle'%3Ek%3C/text%3E%3C/svg%3E"
)

# Everything in the export is inline-styled with no classes, so these rules
# target structure (and lean on !important to beat the inline styles).
SITE_CSS = """<style>
/* Wordmark reveal: at the top of the home page the hero already says
   "made by kas", so the nav repeats it. Hide the nav copy until the hero has
   scrolled away — on About/project pages there is no hero, so it stays put. */
nav > div > a:first-child {
  opacity: 0;
  transform: translateY(-4px);
  pointer-events: none;
  transition: opacity .4s ease, transform .4s ease;
}
html.mbk-scrolled nav > div > a:first-child {
  opacity: 1;
  transform: none;
  pointer-events: auto;
}
@media (prefers-reduced-motion: reduce) {
  nav > div > a:first-child { transition: none; }
}

/* Home project cards: two per row, so each reads as a piece of work rather
   than a thumbnail. */
[data-cards] { grid-template-columns: repeat(2, minmax(0, 1fr)) !important; }

/* Project hero: edge to edge, at the image's own proportions so nothing is
   cropped and no letterbox bars appear. */
[data-hero-frame] {
  width: 100vw !important;
  max-width: 100vw !important;
  margin-left: calc(50% - 50vw) !important;
  margin-right: calc(50% - 50vw) !important;
  aspect-ratio: auto !important;
  height: auto !important;
  max-height: none !important;
  border-radius: 0 !important;
}
[data-hero-frame] image-slot { height: auto !important; display: block; }

/* Project galleries: one image per row, full width of the page. */
[data-gallery] {
  grid-template-columns: 1fr !important;
  max-width: none;
}

/* Nothing is cropped anywhere: every frame takes its image's own ratio
   instead of a fixed 4:3, so "cover" has nothing left to cut off. */
[data-cards] > div > div > div {
  aspect-ratio: auto !important;
  height: auto !important;
}
[data-cards] image-slot { height: auto !important; display: block; }

/* The lightbox is gone, so stop advertising it. */
[data-gframe], [data-hero-frame] { cursor: default !important; }
[data-gallery] [data-gframe] {
  aspect-ratio: auto !important;
  height: auto !important;
}
[data-gallery] [data-gframe] image-slot {
  height: auto !important;
  display: block;
}

@media (max-width: 760px) {
  /* One card per row on a phone — two would be postage stamps. */
  [data-cards] { grid-template-columns: 1fr !important; gap: 36px !important; }

  [data-gallery] { gap: 28px !important; }

  /* The nav wrapped onto two crowded rows and ate a third of the screen.
     Five links can't share one row at this width, so centre them and let the
     wrap read as two deliberate rows rather than a stranded Contact pill. */
  nav > div { padding: 10px 20px !important; gap: 8px !important; }
  nav > div > div {
    gap: 16px !important;
    row-gap: 8px !important;
    width: 100% !important;
    justify-content: center !important;
  }
  nav > div > div > a { font-size: 14px !important; }
  nav > div > div > a:last-child { padding: 7px 16px !important; }
  nav > div > a:first-child { font-size: 16px !important; }

  /* Hero: less dead space above the fold, larger headline relative to screen. */
  header[data-screen-label="Home hero"] {
    padding-top: 64px !important;
    padding-bottom: 52px !important;
  }
  header[data-screen-label="Home hero"] h1 { font-size: 15vw !important; }
  header[data-screen-label="Home hero"] p {
    font-size: 17px !important;
    max-width: 100% !important;
    margin-top: 22px !important;
  }

  /* Section headings and their number labels. */
  section h2 { font-size: 30px !important; }

  /* Desktop section padding leaves a dead void between blocks on a phone. */
  section { padding-top: 44px !important; padding-bottom: 44px !important; }

  /* Nothing should ever scroll sideways on a phone. */
  html, body { overflow-x: hidden !important; }
  img, svg, video { max-width: 100% !important; }
}

@media (max-width: 420px) {
  /* Below this the five nav links can't share a row legibly; let them wrap
     but keep them tight rather than sprawling. */
  nav > div > div { gap: 12px !important; }
  nav > div > div > a { font-size: 13px !important; }
}
</style>"""

META_TAGS = """<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="icon" href="{icon}">
<meta property="og:type" content="website">
<meta property="og:url" content="{url}/">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:image" content="{url}/og-image.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:site_name" content="made by kas">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{desc}">
<meta name="twitter:image" content="{url}/og-image.jpg">""".format(
    title=SITE_TITLE, desc=SITE_DESC, url=SITE_URL, icon=FAVICON
)

# The CSS is kept out of the .format() above on purpose — it's full of braces.
HEAD_INJECT = SITE_CSS + "\n" + META_TAGS

HISTORY_SETUP = """
    %s
    this._navFromHash = () => {
      const h = (location.hash || '').replace(/^#\\/?/, '');
      if (!h) return { view: 'home', projectId: null, section: '' };
      if (h === 'about') return { view: 'about', projectId: null, section: '' };
      if (h.indexOf('project/') === 0) {
        const id = h.slice(8);
        if (this.projects.some(p => p.id === id)) {
          return { view: 'project', projectId: id, section: '' };
        }
        return { view: 'home', projectId: null, section: '' };
      }
      return { view: 'home', projectId: null, section: h };
    };
    this._navApply = (s) => {
      const st = s || { view: 'home', projectId: null, section: '' };
      if (st.view === 'project') {
        this.setState({ view: 'project', projectId: st.projectId, activeSection: '', zoom: null });
        this._scheduleRemount();
        setTimeout(() => window.scrollTo({ top: 0 }), 0);
      } else if (st.view === 'about') {
        this.setState({ view: 'about', projectId: null, activeSection: '', zoom: null });
        setTimeout(() => window.scrollTo({ top: 0 }), 0);
      } else {
        this.setState({ view: 'home', projectId: null, zoom: null });
        if (st.section) setTimeout(() => this.scrollToId(st.section), 80);
        else setTimeout(() => window.scrollTo({ top: 0 }), 0);
      }
    };
    this._navPush = (st, hash) => {
      try { history.pushState(st, '', hash); } catch (err) { /* file:// */ }
    };
    // The image-slot component reads its picture only when it mounts. Moving
    // between projects reuses the same elements and just swaps their id, so the
    // component drops the old image and looks for a per-slot .state.json that
    // does not exist here — every gallery image went blank. Detaching and
    // reinserting the same node re-runs its mount and it reads the embedded
    // image again. Reinserting the SAME node (rather than a clone) keeps
    // React's reference to it intact.
    this._remountSlots = () => {
      document.querySelectorAll('image-slot').forEach((slot) => {
        const img = slot.shadowRoot && slot.shadowRoot.querySelector('img');
        if (img && img.naturalWidth > 0) return;
        const parent = slot.parentNode;
        if (!parent) return;
        const next = slot.nextSibling;
        parent.removeChild(slot);
        parent.insertBefore(slot, next);
      });
    };
    // Slots mount over a few frames, so sweep a few times rather than guessing
    // one delay. Slots that are legitimately empty simply stay empty.
    this._scheduleRemount = () => {
      if (this._remountTimers) this._remountTimers.forEach(clearTimeout);
      this._remountTimers = [60, 250, 700].map((d) => setTimeout(this._remountSlots, d));
    };
    // Each image-slot carries an aspect ratio chosen in the editor (3/2, 4/3,
    // 16/9) and crops the photo to fit it. The image's real proportions are
    // only knowable once it has decoded, so match the slot to the image at
    // runtime — then "cover" has nothing left to crop and no letterbox bars
    // appear. Cheap enough to re-assert every frame, which also survives the
    // component rewriting its own style on re-render.
    this._fitRatios = () => {
      document.querySelectorAll('image-slot').forEach((slot) => {
        const img = slot.shadowRoot && slot.shadowRoot.querySelector('img');
        if (!img || !img.naturalWidth || !img.naturalHeight) return;
        const ratio = img.naturalWidth + ' / ' + img.naturalHeight;
        if (slot.style.getPropertyValue('aspect-ratio') !== ratio) {
          slot.style.setProperty('aspect-ratio', ratio, 'important');
        }
        if (slot.style.getPropertyValue('height') !== 'auto') {
          slot.style.setProperty('height', 'auto', 'important');
        }
      });
    };
    // An interval rather than requestAnimationFrame: rAF is suspended while
    // the tab is in the background, which would leave ratios unapplied on a
    // restored tab.
    this._fitTimer = setInterval(this._fitRatios, 120);
    this._fitRatios();
    this._syncWordmark = () => {
      const hero = document.querySelector('header[data-screen-label="Home hero"]');
      // No hero (About / project pages) means the nav wordmark is the only one.
      const overHero = !!hero && window.scrollY < Math.max(80, hero.offsetHeight * 0.5);
      document.documentElement.classList.toggle('mbk-scrolled', !overHero);
    };
    window.addEventListener('scroll', this._syncWordmark, { passive: true });
    // Views swap by re-render, not navigation, so poll cheaply for the hero
    // appearing or disappearing rather than wiring into every transition.
    this._wordmarkTimer = setInterval(this._syncWordmark, 200);
    this._syncWordmark();
    this._onPop = (e) => { this._navApply((e && e.state) || this._navFromHash()); };
    window.addEventListener('popstate', this._onPop);
    const initialNav = this._navFromHash();
    try {
      history.replaceState(initialNav, '', location.hash || location.pathname + location.search);
    } catch (err) { /* file:// */ }
    if (initialNav.view !== 'home' || initialNav.section) {
      setTimeout(() => this._navApply(initialNav), 60);
    }
""" % MARK

# (description, old, new, expected occurrences) applied to the template.
TEMPLATE_EDITS = [
    (
        "page metadata + favicon",
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n' + HEAD_INJECT,
        1,
    ),
    ("html lang", "<html><head>", '<html lang="en"><head>', 1),
    (
        # Images are shown large inline now, so the lightbox has no purpose.
        "remove click-to-zoom",
        "  onDocClick(e) {\n    const path = e.composedPath ? e.composedPath() : [];",
        "  onDocClick(e) {\n    return; /* zoom removed: images are shown large inline */\n    const path = e.composedPath ? e.composedPath() : [];",
        1,
    ),
    (
        "home card grid -> stylesheet control",
        '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:56px 36px;margin-top:48px">',
        '<div data-cards="" style="display:grid;gap:56px 36px;margin-top:48px">',
        2,
    ),
    (
        "project gallery grid -> stylesheet control",
        '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:44px 32px;margin-top:64px">',
        '<div data-gallery="" style="display:grid;gap:44px 32px;margin-top:64px">',
        1,
    ),
    (
        "bigger hero headline",
        "font-size:clamp(36px,6vw,88px);line-height:1.05",
        "font-size:clamp(44px,8vw,116px);line-height:1.02",
        1,
    ),
    (
        "bigger hero intro copy",
        "max-width:520px;font-size:clamp(16px,1.6vw,19px)",
        "max-width:640px;font-size:clamp(17px,1.9vw,22px)",
        1,
    ),
    (
        # A hard break mid-sentence orphaned "to last." onto its own line at
        # every width, and looked especially broken on a phone.
        "forced line break in hero copy",
        "and made <br>to last.",
        "and made to last.",
        1,
    ),
    (
        # The home-grid card has the real name hardcoded in the markup, but the
        # detail page reads this array — so the page headed itself "Project Title".
        "unfilled project title (Box Bites Cafe)",
        "{ id: 'paper-trail', title: 'Project Title'",
        "{ id: 'paper-trail', title: 'Box Bites Café'",
        1,
    ),
    (
        # Same array-vs-markup split: the card reads "Lil Sprouts Lab" while the
        # detail page and the prev/next links read "Lil sprouts lab".
        "project title casing (Lil Sprouts Lab)",
        "{ id: 'arc-lamp', title: 'Lil sprouts lab'",
        "{ id: 'arc-lamp', title: 'Lil Sprouts Lab'",
        1,
    ),
    (
        "footer email (domain has no mail server)",
        "mailto:hello@madebykas.com",
        "mailto:kasshirawat@gmail.com",
        1,
    ),
    (
        "Instagram profile link",
        'href="https://instagram.com"',
        'href="https://www.instagram.com/madebykas_/"',
        2,
    ),
    (
        "LinkedIn profile link",
        'href="https://linkedin.com"',
        'href="https://www.linkedin.com/in/madebykas/"',
        2,
    ),
    (
        "history: install listeners",
        "    window.addEventListener('scroll', this._onScroll, { passive: true });\n  }",
        "    window.addEventListener('scroll', this._onScroll, { passive: true });\n"
        + HISTORY_SETUP
        + "  }",
        1,
    ),
    (
        "history: tear down listeners",
        "    window.removeEventListener('scroll', this._onScroll);",
        "    window.removeEventListener('scroll', this._onScroll);\n"
        "    window.removeEventListener('popstate', this._onPop);\n"
        "    window.removeEventListener('scroll', this._syncWordmark);\n"
        "    clearInterval(this._wordmarkTimer);\n"
        "    if (this._remountTimers) this._remountTimers.forEach(clearTimeout);\n"
        "    clearInterval(this._fitTimer);",
        1,
    ),
    (
        "history: section links",
        "  goSection(id) {\n    if (this.state.view !== 'home') {",
        "  goSection(id) {\n"
        "    this._navPush({ view: 'home', projectId: null, section: id }, '#/' + id);\n"
        "    if (this.state.view !== 'home') {",
        1,
    ),
    (
        "history: project pages",
        "  openProject(id) {\n    this.setState({ view: 'project', projectId: id, activeSection: '' });",
        "  openProject(id) {\n"
        "    this._navPush({ view: 'project', projectId: id, section: '' }, '#/project/' + id);\n"
        "    this.setState({ view: 'project', projectId: id, activeSection: '' });\n"
        "    if (this._scheduleRemount) this._scheduleRemount();",
        1,
    ),
    (
        "history: logo / home",
        "      goHome: () => {\n        this.setState({ view: 'home', projectId: null });",
        "      goHome: () => {\n"
        "        this._navPush({ view: 'home', projectId: null, section: '' }, '#/');\n"
        "        this.setState({ view: 'home', projectId: null });",
        1,
    ),
    (
        "history: about",
        "      goAbout: () => {\n        this.setState({ view: 'about', projectId: null, activeSection: '' });",
        "      goAbout: () => {\n"
        "        this._navPush({ view: 'about', projectId: null, section: '' }, '#/about');\n"
        "        this.setState({ view: 'about', projectId: null, activeSection: '' });",
        1,
    ),
]

# Applied to the outer loader page — this is all a non-JS crawler
# (WhatsApp, LinkedIn, Slack link previews) ever sees.
WRAPPER_EDITS = [
    ("loader metadata", "<title>Bundled Page</title>", META_TAGS, 1),
    ("loader html lang", "<html>\n<head>", '<html lang="en">\n<head>', 1),
]

# Whole blocks that go away entirely; each asserts its match count.
TEMPLATE_CUTS = [
    ("Archive section", re.compile(r'\n  <!-- The Archieve -->.*?\n  </section>\n', re.S), 1),
    ("Archive nav link and hero pill", re.compile(r'<a sc-camel-on-click="\{\{goArt\}\}".*?</a>', re.S), 2),
]

TEMPLATE_RE = re.compile(r'(<script type="__bundler/template">)(.*?)(</script>)', re.S)


def apply_edits(text, edits, where):
    for desc, old, new, expected in edits:
        found = text.count(old)
        if found != expected:
            sys.exit(
                "error: [%s] %s matched %d times, expected %d.\n"
                "The export's structure changed — update scripts/patch-export.py."
                % (where, desc, found, expected)
            )
        text = text.replace(old, new)
    return text


def main():
    if len(sys.argv) != 3:
        sys.exit("usage: patch-export.py <exported.html> <output.html>")
    src, dst = sys.argv[1], sys.argv[2]

    bundle = open(src, encoding="utf-8").read()
    if MARK in bundle:
        sys.exit("error: this file is already patched — pass the raw export")

    m = TEMPLATE_RE.search(bundle)
    if not m:
        sys.exit("error: no __bundler/template script found — is this a bundle export?")

    template = json.loads(m.group(2))
    for desc, rx, expected in TEMPLATE_CUTS:
        found = len(rx.findall(template))
        if found != expected:
            sys.exit(
                "error: [cut] %s matched %d times, expected %d.\n"
                "The export's structure changed — update scripts/patch-export.py."
                % (desc, found, expected)
            )
        template = rx.sub("", template)
    template = apply_edits(template, TEMPLATE_EDITS, "template")
    # The template embeds its own <script> tags, so "</" must stay escaped or
    # the outer script tag closes early — the bundler writes it as </.
    encoded = json.dumps(template).replace("</", "<\\u002F")
    patched = bundle[: m.start(2)] + encoded + bundle[m.end(2) :]
    patched = apply_edits(patched, WRAPPER_EDITS, "wrapper")

    open(dst, "w", encoding="utf-8").write(patched)
    print("patched %s -> %s (%d bytes)" % (src, dst, len(patched)))


if __name__ == "__main__":
    main()
