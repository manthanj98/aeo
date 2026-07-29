#!/usr/bin/env python3
"""Assemble the Pepper Project dashboard into one self-contained HTML file.

Everything is inlined — React, ReactDOM, the dc-runtime template engine, the
theme and the app — so the published page issues no external requests and works
under the artifact host's strict CSP (and straight off the filesystem).

    python3 build.py            -> dist/pepper-project.html
    python3 build.py --standalone  also emit a full <html> doc for local testing

The artifact host wraps the published file in <!doctype html><head></head><body>,
so the default output is a body fragment: scripts, then <style>, then the markup.
"""

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).parent
SRC = ROOT / "src"
VENDOR = ROOT / "vendor"
DIST = ROOT / "dist"

TITLE = "Acme · AI Visibility Dashboard"
DESCRIPTION = "Answer-engine optimisation analytics: visibility, citations, prompts and competitors across five AI engines."


def read(path: pathlib.Path) -> str:
    if not path.exists():
        sys.exit(f"build: missing required file {path}")
    return path.read_text()


def build(standalone: bool = False) -> str:
    react = read(VENDOR / "react.production.min.js")
    react_dom = read(VENDOR / "react-dom.production.min.js")
    runtime = read(VENDOR / "dc-runtime.js")
    theme = read(SRC / "theme.css")
    template = read(SRC / "app.template.html")
    logic = read(SRC / "app.logic.js")

    # The runtime boots on DOMContentLoaded and needs window.React/ReactDOM
    # already present, so vendor scripts must precede it. Inline <script> tags
    # execute in document order, which guarantees that.
    parts = [
        f"<script>{react}\n</script>",
        f"<script>{react_dom}\n</script>",
        f"<script>{runtime}\n</script>",
        f"<style>\n{theme}\n</style>",
        template.strip(),
        f'<script type="text/x-dc" data-dc-script="">\n{logic}\n</script>',
    ]
    body = "\n".join(parts)

    if not standalone:
        return f"<title>{TITLE}</title>\n<meta name=\"description\" content=\"{DESCRIPTION}\">\n{body}\n"

    return (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
        f"<title>{TITLE}</title>\n</head>\n<body>\n{body}\n</body>\n</html>\n"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--standalone", action="store_true",
                    help="emit a complete <html> document (for local browser testing)")
    ap.add_argument("-o", "--out", default=None)
    args = ap.parse_args()

    DIST.mkdir(exist_ok=True)
    out = pathlib.Path(args.out) if args.out else DIST / (
        "pepper-project.standalone.html" if args.standalone else "pepper-project.html")
    html = build(standalone=args.standalone)
    out.write_text(html)
    print(f"build: wrote {out} ({len(html):,} bytes)")


if __name__ == "__main__":
    main()
