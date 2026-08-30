---
name: infdc-overlay-template
description: Modify OBS browser-source HTML/CSS templates and exported overlay views for the INFINITAS daken counter.
---

# Infdc Overlay Template

Use this skill when editing HTML, CSS, JavaScript, or template output used by OBS browser sources, local docs previews, or score/result overlay views.

## Core Files

- `template/*.html`: packaged browser-source templates.
- `template/v2/*.html`: newer result/history views; keep parity with equivalent older templates when intended.
- `docs/index.html` and `docs/base.css`: documentation or preview pages.
- `export/jquery-3.6.4.min.js`: bundled library; do not edit minified vendor code unless explicitly asked.
- `src/websocket_server.py` and related Python writers may define the data contract consumed by templates.

## Design and Compatibility

- This is an OBS overlay, so prioritize stable layout, readable numbers, and predictable dimensions over decorative page structure.
- Avoid changing IDs, expected data attributes, or script-visible element names until you have traced their producers and consumers.
- When changing result/history/today views, search for equivalent markup in `template/` and `template/v2/` so visual or data behavior does not drift accidentally.
- CSS commonization is welcome when it removes real duplication, but keep the generated/package layout simple.
- Be careful with Japanese song names, long option strings, score deltas, and narrow OBS browser-source dimensions.

## Verification

- For static HTML/CSS changes, inspect affected templates and search for referenced selectors or IDs.
- If no browser or OBS preview is run, state that layout remains visually unverified.
- Do not run release packaging just to validate template changes.
