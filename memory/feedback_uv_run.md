---
name: Use uv run for CLI testing
description: User prefers `uv run hassle` over activating the venv or using `.venv/bin/hassle`
type: feedback
---

Use `uv run hassle` to test the CLI, not `.venv/bin/hassle` or activating the venv.

**Why:** This is a uv-managed project; `uv run` handles the venv automatically.
**How to apply:** Whenever verifying the CLI works, use `uv run hassle`.
