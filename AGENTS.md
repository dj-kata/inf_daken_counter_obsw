# AGENTS.md

## Repository Rules

- Do not create, delete, recreate, replace, or otherwise modify `.venv`.
- Do not run commands that may automatically rebuild `.venv`, including `uv run` or `uv sync`, unless the user explicitly asks for it in that turn.
- If dependency-backed commands are needed, prefer tools that use the existing environment without mutating `.venv`; ask before any command that might change it.
