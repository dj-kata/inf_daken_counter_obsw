---
name: infdc-release-build
description: Prepare or inspect release packaging for the INFINITAS daken counter without treating build steps as routine validation.
---

# Infdc Release Build

Use this skill for release preparation, packaging investigation, version updates, and build/distribution issues. Do not use it for ordinary bug-fix verification unless the user asks about packaging or release artifacts.

## Core Files

- `Makefile`: defines `all`, `top`, `dist`, `clean`, and `test` targets.
- `setup.py`: cx_Freeze packaging entrypoint.
- `pyproject.toml` and `uv.lock`: dependency declarations and lockfile.
- `version.txt`: release version copied into the built package.
- `template/`, `songinfo.infdc`, and `infnotebook/resources`: release payload inputs.

## Important Constraints

- Repository rules prohibit creating, deleting, rebuilding, or implicitly mutating `.venv`.
- `make` targets invoke Windows `uv` via `/mnt/c/Users/katao/.local/bin/uv.exe` and may create or replace `inf_daken_counter/` and `inf_daken_counter.zip`.
- Ask before running commands that may rebuild dependencies, package the app, or modify generated distribution directories.
- Treat `infnotebook/resources` as required release input. If it is missing or stale, report that rather than inventing substitutes.

## Release Workflow Guidance

- Before packaging, check `git status --short` and avoid mixing unrelated dirty changes into release notes or artifacts.
- Confirm `version.txt` and the intended version bump before editing.
- When inspecting packaging bugs, trace `Makefile` copy/delete steps and `setup.py` options before changing source code.
- Keep generated artifacts out of commits unless the user explicitly wants them tracked.

## Verification

- Prefer read-only inspection unless the user asked for a build.
- If a build is requested and permitted, report the created artifact path and any skipped live checks.
