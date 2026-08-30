---
name: infdc-obs-websocket
description: Debug or extend OBS control, OBS WebSocket connection handling, and daken counter WebSocket broadcasts.
---

# Infdc OBS WebSocket

Use this skill for work involving OBS connection state, scene/source selection, scene switching, browser-source updates, or the app's local WebSocket data feed.

## Core Files

- `src/obs_websocket_manager.py`: OBS WebSocket connection lifecycle and OBS API calls.
- `src/obs_dialog.py`: OBS settings and scene/source selection UI.
- `src/obs_control.py`: higher-level OBS actions.
- `src/websocket_server.py`: local browser-source data broadcasting.
- `src/config.py` and `src/config_dialog.py`: OBS-related settings may be persisted or exposed in the settings UI.

## Investigation Guidance

- Separate OBS WebSocket concerns from the local browser-source WebSocket server; they use different connection models and failure modes.
- When scene or source lists are stale, look for caching, reconnect, scene collection changes, and refresh timing before changing UI presentation.
- For scene collection switching issues, verify whether the code re-queries OBS after collection changes or only at dialog initialization.
- Preserve graceful failure behavior. OBS may be closed, unreachable, password-protected, or temporarily reconnecting.
- Keep network operations bounded and avoid blocking the UI thread.

## Verification

- Run static Python checks where possible.
- If live OBS is unavailable, clearly mark live connection behavior as unverified and describe the manual scenario to test: connect, change scene collection, reopen/refresh dialog, confirm scene/source list, trigger configured action.
- Avoid requiring OBS-specific commands or credentials unless the user explicitly asks to run an integration check.
