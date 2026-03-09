# Claude Code Instructions for duploctl

@.github/copilot-instructions.md
@.github/agents/coder.agent.md
@.github/instructions/py.instructions.md
@.github/instructions/yaml.instructions.md

## Claude Code Tool Notes

The .github instructions reference VS Code tasks. Since Claude Code uses the terminal directly, use these equivalents:

| VS Code Task   | Terminal Command                                   |
|----------------|----------------------------------------------------|
| Pip Install    | `pip install --editable '.[build,test,aws,docs]'`  |
| Unit Test      | `pytest src -m unit`                               |
| Ruff Lint      | `ruff check src`                                   |
| Build Package  | `python -m build`                                  |
| Docs Serve     | `mkdocs serve`                                     |
| Docs Build     | `mkdocs build`                                     |
