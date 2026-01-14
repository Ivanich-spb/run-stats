# Repository Guidelines

## Project Structure & Module Organization
This repository is starting a new project. Keep a clear separation between specs, code, and tests:
- `features/`: BDD specifications in `.feature` files (source of truth).
- `src/`: application code that implements the specs.
- `tests/`: step definitions and test helpers for `pytest-bdd`.
- `README.md`: project overview and constraints.
- `AGENTS.md`: contributor guide and workflow rules.
Add other top-level folders only when they are stable and documented.

## Build, Test, and Development Commands
Commands should be explicit and reproducible. Once tooling is added, document the exact commands here. Example targets to include:
- `python -m pytest`: run the test suite.
- `python -m pytest -k <name>`: run a focused test slice.
- `make test`: optional convenience wrapper for CI parity.
If you add scripts, keep them in a `scripts/` folder and mention them here.

## Vibe Coding & BDD Workflow
This project uses a Vibe Coding approach where BDD is the specification and AI is a co-author.
Workflow rules:
- Write or update `.feature` files first, before any implementation.
- Implement step definitions next, then application code to satisfy them.
- Keep scenarios short and user-focused; prefer Given/When/Then with clear nouns.
- Treat failing scenarios as the queue; do not merge code without green tests.
- Work only on one task at a time and only in the `main` branch.

## Coding Style & Naming Conventions
Until a formatter is chosen, keep style simple and consistent:
- Python: 4-space indentation; snake_case for functions and variables.
- Files: lowercase names with underscores (for example `run_tracker.py`).
- Feature files: kebab-case (for example `record-run.feature`).
When a formatter/linter is introduced, enforce it in CI and update this section.

## Testing Guidelines
Testing is mandatory and test-first:
- Framework: `pytest-bdd` with `.feature` files in `features/`.
- Step definitions live in `tests/` and must map 1:1 to scenarios.
- Add tests before code, and keep new functionality covered by scenarios.
Document any fixtures or shared setup in `tests/conftest.py`.

## Task Intake & Execution Order
Follow this sequence for every task:
1) Read the task fully. Confirm the "Why", "What", "How", and Acceptance Criteria are understood.
2) Write or update `.feature` scenarios that cover Acceptance Criteria (behavior-focused).
3) Implement step definitions in `tests/` and run tests to see them fail (Red).
4) Write the minimal application code to make tests pass (Green).
5) Refactor without changing behavior; tests must still pass.
6) Commit with a meaningful message.
If the task is unclear, stop and report the block; do not proceed.
Do not fix bugs or make improvements outside the current task scope.

## Commit & Pull Request Guidelines
Commits must show evolution and intent:
- Use short, imperative, sentence-case messages (for example "Add first run scenario").
- Prefer small commits that each move the spec or implementation forward.
Pull requests should include:
- Summary of scenarios added/changed and current status.
- How to run tests locally.
- Any open questions or known gaps.

## Documentation & Run Instructions
Maintain `README.md`, `AGENTS.md`, and a clear run guide. The run guide should include:
- Prerequisites (Python version, env setup).
- How to run tests and the app (if applicable).

## Security & Configuration Tips
Never commit secrets. If configuration is needed, use example files like `.env.example` and document required variables in the run guide.
