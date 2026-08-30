---
name: infdc-maintenance
description: Maintain the INFINITAS daken counter project for routine bug fixes, feature additions, and repository orientation.
---

# Infdc Maintenance

Use this skill for ordinary development in `inf_daken_counter_obsw`: bug fixes, small features, refactors, and codebase orientation that are not more specifically covered by another `infdc-*` skill.

## Project Shape

- The app is a Python desktop tool for beatmania IIDX INFINITAS daken counting with OBS/WebSocket and browser-source output.
- Main application code lives in `src/`; GUI wrapper modules live in `gui/`; OBS/browser templates live in `template/`; release packaging is driven by `Makefile`.
- `infnotebook/` is an external codebase copied into the workspace. Treat it as vendored/upstream-like unless the task explicitly targets it.

## Start Points

- Read `AGENTS.md` before any command that might touch dependencies. It forbids creating, deleting, rebuilding, or implicitly mutating `.venv`.
- For product context, read `README.md` and the relevant lines of `TODO.md`.
- Use `rg`/`rg --files` first when locating code.
- Check `git status --short` early and preserve unrelated user changes.

## Development Guidance

- Prefer existing local patterns over new abstractions. This codebase favors direct Python modules and simple data flow.
- When adding or changing settings, also consider `infdc-ui-settings`.
- When touching OBS scene/source behavior or WebSocket behavior, also consider `infdc-obs-websocket`.
- When touching browser-source HTML/CSS, also consider `infdc-overlay-template`.
- Avoid commands that may rebuild `.venv`, especially `uv run` and `uv sync`, unless the user explicitly asks in the current turn.

## Verification

- For Python-only changes, run the narrowest safe check available without mutating `.venv`, such as `python3 -m py_compile` on touched modules.
- If a change needs the Windows app, OBS, capture hardware, or live INFINITAS state, explain the unverified boundary clearly.
- Do not use the `Makefile` build targets as routine validation; they use Windows `uv` and packaging side effects.
