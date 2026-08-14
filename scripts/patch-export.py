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
  nav       the Archive nav label carried a stray leading &nbsp;.
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

@media (max-width: 760px) {
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
    ("stray nbsp in Archive nav label", ">&nbsp;Archive<", ">Archive<", 1),
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
        "    clearInterval(this._wordmarkTimer);",
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
        "    this.setState({ view: 'project', projectId: id, activeSection: '' });",
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

    template = apply_edits(json.loads(m.group(2)), TEMPLATE_EDITS, "template")
    # The template embeds its own <script> tags, so "</" must stay escaped or
    # the outer script tag closes early — the bundler writes it as </.
    encoded = json.dumps(template).replace("</", "<\\u002F")
    patched = bundle[: m.start(2)] + encoded + bundle[m.end(2) :]
    patched = apply_edits(patched, WRAPPER_EDITS, "wrapper")

    open(dst, "w", encoding="utf-8").write(patched)
    print("patched %s -> %s (%d bytes)" % (src, dst, len(patched)))


if __name__ == "__main__":
    main()
