---
trigger: glob
globs: src/tests/**/*.py
---
@../../.github/instructions/py.instructions.md
@../../.github/agents/coder.agent.md
**Critical:** Run only unit tests (`pytest src -m unit`) unless explicitly approved for integration tests.
