# AGENTS.md

## 1. General Principles

- Before making changes, inspect the relevant code, project structure, and existing implementation patterns.
- Follow the existing architecture, coding conventions, naming conventions, and dependency choices.
- Prefer simple, maintainable solutions over unnecessary abstractions or complexity.
- Reuse existing functions, components, and utilities whenever practical.
- Keep changes focused on the requested task. Avoid unrelated refactoring, formatting, or cleanup.
- Do not introduce new dependencies unless they provide a clear benefit and are necessary for the task.
- Preserve backward compatibility and existing behavior unless the requested feature explicitly requires a change.
- Do not modify unrelated files or overwrite existing user changes.

## 2. Autonomy and Decision-Making

- Handle routine implementation decisions autonomously without requesting confirmation.
- Ask questions only when ambiguity materially affects expected behavior, compatibility, security, or architecture.
- When multiple reasonable implementations exist, prefer the simplest approach consistent with the current codebase.
- Make reasonable assumptions for minor unspecified details and document them in the final response when relevant.
- Do not stop at analysis or recommendations when the user has explicitly requested implementation.
- If an approach fails, investigate the cause and attempt a reasonable alternative before asking for assistance.
- Avoid unnecessary back-and-forth when the task can be completed safely using existing project conventions.

## 3. Planning and Implementation

- For small or straightforward tasks, proceed directly with implementation.
- For complex or cross-cutting changes, briefly outline the implementation plan before modifying code.
- Identify the relevant files and understand their relationships before making changes.
- Prefer incremental, logically grouped changes over broad rewrites.
- Address the root cause of problems rather than adding superficial workarounds.
- Avoid speculative improvements or implementing features beyond the requested scope.
- Keep public APIs, configuration formats, and persisted data compatible unless changes are explicitly required.
- Update relevant documentation when behavior, configuration, or usage changes.

## 4. Environment and Dependency Safety

### Protected Environment

- The existing project `.venv` is owned and managed by the user.
- Never create, delete, recreate, replace, or modify the project `.venv` or any files within it.
- Never install, upgrade, or remove packages in the protected `.venv`.
- Never run commands that may modify the protected `.venv`, including `uv run` or `uv sync` when they target that environment.
- Treat other existing virtual environments as user-managed unless explicitly identified as Codex-owned.
- Do not modify dependency manifests or lockfiles solely for environment setup or testing.

### Codex-Managed Environment

- You may create and manage a separate virtual environment for development, testing, and verification without asking for permission.
- Prefer `.codex-venv` in the repository root for this purpose.
- You may install, upgrade, or remove dependencies within `.codex-venv` as needed.
- You may recreate or delete `.codex-venv` when necessary, provided it is Codex-owned.
- Never redirect Codex-managed environment operations to the protected `.venv`.
- Ensure `.codex-venv` is excluded from Git tracking, preferably through `.git/info/exclude` or an existing ignore rule.
- Avoid making unnecessary changes to tracked project files when configuring the Codex environment.

### Command Execution

- Explicitly target `.codex-venv` when installing dependencies or running environment-management commands.
- When using `uv`, specify the intended environment explicitly and verify that the command will not target `.venv`.
- Prefer invoking the Codex-managed environment's Python and tools directly.
- Do not rely on implicit virtual environment selection when there is a risk of modifying the protected `.venv`.
- If a command cannot be executed without risking changes to `.venv`, use an alternative approach or ask for confirmation.

### Verification

- Use the Codex-managed environment for tests, linting, type checking, and other verification tasks whenever practical.
- If the Codex-managed environment differs from the user's environment, report any compatibility limitations.
- Never modify the protected environment to make tests or builds pass.
- If verification is impossible without accessing or modifying protected resources, explain the limitation.

## 5. Testing and Verification

- Add or update tests when implementing new behavior, fixing bugs, or changing existing functionality, where appropriate.
- Prefer focused tests covering the changed behavior and relevant edge cases.
- Run relevant tests, linters, and type checks when the environment permits.
- Use existing project verification commands and conventions.
- If verification fails, investigate the failure and determine whether it was introduced by the current changes.
- Fix failures caused by the current changes when feasible.
- Do not remove, disable, or weaken existing tests merely to make verification pass.
- Do not modify unrelated code solely to address pre-existing test failures.
- Never claim that tests passed unless they were actually executed successfully.
- Clearly distinguish verified behavior from assumptions or untested behavior.

## 6. Self-Review

After implementation, review the changes before reporting completion.

- Inspect `git diff` and confirm that all changes are intentional and relevant.
- Check for regressions, edge cases, compatibility issues, and unnecessary complexity.
- Look for duplicated logic that could reuse existing code.
- Verify that error handling follows existing project conventions.
- Check whether new dependencies, configuration changes, or documentation updates are actually necessary.
- Remove temporary debugging code, unused imports, and accidental modifications.
- Correct issues discovered during self-review when they are within the task scope.

## 7. Git and File Safety

- Do not run `git commit`, `git push`, `git reset`, `git clean`, or other potentially destructive Git operations unless explicitly instructed.
- Do not discard, overwrite, or revert user changes.
- Do not modify files unrelated to the current task.
- Avoid broad automated formatting that produces unrelated diffs.
- Do not modify secrets, credentials, or environment-specific configuration unless explicitly required.
- Never expose secrets in source code, logs, or final responses.

## 8. Completion Report

After completing a task, provide a concise report containing:

1. **Changes:** What was implemented or fixed.
2. **Files:** The main files that were changed.
3. **Verification:** Tests, checks, or builds executed and their results.
4. **Limitations:** Anything not verified, unresolved issues, or relevant concerns.

- Keep the report concise and focused on actionable information.
- Do not provide lengthy explanations of routine implementation details unless requested.
- Clearly state when a task is only partially completed.
- Do not claim completion if the requested functionality has not been implemented.