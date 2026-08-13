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
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n' + META_TAGS,
        1,
    ),
    ("html lang", "<html><head>", '<html lang="en"><head>', 1),
    ("stray nbsp in Archive nav label", ">&nbsp;Archive<", ">Archive<", 1),
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
        "    window.removeEventListener('popstate', this._onPop);",
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
