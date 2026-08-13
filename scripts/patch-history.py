#!/usr/bin/env python3
"""Add browser back/forward support to an exported bundle.

The export navigates purely by React state, so the URL never changes and the
browser keeps a single history entry — pressing Back leaves the site entirely.
This rewrites the component to push a history entry per view and to restore
state on popstate, which also makes sections and projects deep-linkable.

Re-run this on every new export:

    python3 scripts/patch-history.py ~/Downloads/NEW.html index.html

Every replacement below is asserted, so if a future export renames these
methods the script fails loudly instead of silently producing an unpatched
page.
"""
import json
import re
import sys

MARK = "/* history-nav: added post-export */"

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

REPLACEMENTS = [
    # 1. install the history listeners at the end of componentDidMount
    (
        "    window.addEventListener('scroll', this._onScroll, { passive: true });\n  }",
        "    window.addEventListener('scroll', this._onScroll, { passive: true });\n"
        + HISTORY_SETUP
        + "  }",
    ),
    # 2. tear them down again
    (
        "    window.removeEventListener('scroll', this._onScroll);",
        "    window.removeEventListener('scroll', this._onScroll);\n"
        "    window.removeEventListener('popstate', this._onPop);",
    ),
    # 3. section links (Products / Packaging / Archive / Contact)
    (
        """  goSection(id) {
    if (this.state.view !== 'home') {""",
        """  goSection(id) {
    this._navPush({ view: 'home', projectId: null, section: id }, '#/' + id);
    if (this.state.view !== 'home') {""",
    ),
    # 4. opening a project card (also covers prev/next within a project)
    (
        """  openProject(id) {
    this.setState({ view: 'project', projectId: id, activeSection: '' });""",
        """  openProject(id) {
    this._navPush({ view: 'project', projectId: id, section: '' }, '#/project/' + id);
    this.setState({ view: 'project', projectId: id, activeSection: '' });""",
    ),
    # 5. the "made by kas" logo
    (
        """      goHome: () => {
        this.setState({ view: 'home', projectId: null });""",
        """      goHome: () => {
        this._navPush({ view: 'home', projectId: null, section: '' }, '#/');
        this.setState({ view: 'home', projectId: null });""",
    ),
    # 6. the About link
    (
        """      goAbout: () => {
        this.setState({ view: 'about', projectId: null, activeSection: '' });""",
        """      goAbout: () => {
        this._navPush({ view: 'about', projectId: null, section: '' }, '#/about');
        this.setState({ view: 'about', projectId: null, activeSection: '' });""",
    ),
]

TEMPLATE_RE = re.compile(
    r'(<script type="__bundler/template">)(.*?)(</script>)', re.S
)


def patch_template(template):
    if MARK in template:
        sys.exit("error: this export already contains the history patch")
    for i, (old, new) in enumerate(REPLACEMENTS, 1):
        count = template.count(old)
        if count != 1:
            sys.exit(
                "error: replacement %d matched %d times, expected 1.\n"
                "The export's structure changed — update scripts/patch-history.py."
                % (i, count)
            )
        template = template.replace(old, new)
    return template


def main():
    if len(sys.argv) != 3:
        sys.exit("usage: patch-history.py <exported.html> <output.html>")
    src, dst = sys.argv[1], sys.argv[2]

    bundle = open(src, encoding="utf-8").read()
    m = TEMPLATE_RE.search(bundle)
    if not m:
        sys.exit("error: no __bundler/template script found — is this a bundle export?")

    template = patch_template(json.loads(m.group(2)))
    # The template embeds its own <script> tags, so "</" must stay escaped or
    # the outer script tag closes early — the bundler writes it as </.
    encoded = json.dumps(template).replace("</", "<\\u002F")
    patched = bundle[: m.start(2)] + encoded + bundle[m.end(2) :]

    open(dst, "w", encoding="utf-8").write(patched)
    print("patched %s -> %s (%d bytes)" % (src, dst, len(patched)))


if __name__ == "__main__":
    main()
