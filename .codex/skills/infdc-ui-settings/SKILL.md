---
name: infdc-ui-settings
description: Add or fix INFINITAS daken counter configuration, settings dialogs, and Japanese/English UI text.
---

# Infdc UI Settings

Use this skill when the request touches application settings, configuration persistence, labels, dialog controls, or Japanese/English UI strings.

## Core Files

- `src/config.py`: persisted configuration defaults and load/save behavior.
- `src/config_dialog.py`: settings dialog widgets, control state, and signal wiring.
- `src/ui_jp.py` and `src/ui_en.py`: localized labels and user-facing text.
- `src/main_window.py` and `gui/*.py`: call sites that may read or react to config values.

## Change Pattern

- Trace an existing nearby setting before adding a new one. Match its naming, default value style, persistence behavior, and UI wiring.
- Treat config, dialog controls, and both language files as one change surface. A setting is incomplete if it is only persisted or only displayed.
- Keep Japanese and English keys aligned. When adding one language entry, search for the corresponding key in the other file and update both.
- Prefer existing PySide6 widget and layout patterns in `src/config_dialog.py`; avoid restyling or reorganizing unrelated dialog sections.
- If a setting affects runtime behavior, identify where config is consumed and ensure changes apply at the right time: immediately, on restart, or after reconnect.

## Verification

- Run a syntax check on touched Python modules when possible without rebuilding `.venv`.
- For dialog behavior that requires a GUI session, state what was checked statically and what remains manual.
- Watch for user-visible text overflow or untranslated fallback strings when adding longer English labels.
