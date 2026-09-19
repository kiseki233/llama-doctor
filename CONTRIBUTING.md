# Contributing

`llama-doctor` should stay small, local, predictable, and explainable.

## Scope

Good contributions improve command parsing, llama.cpp help parsing, diagnostics, migration safety, tests, packaging, or the lightweight CLI/GUI.

Please do not turn the core project into a model manager, chat frontend, benchmark suite, downloader, or automatic performance tuner.

## Development

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e . pytest
python -m pytest -q
```

For GUI work:

```bash
pip install -e ".[gui]"
```

## Adding a migration rule

Migration rules must be based on documented or independently verified llama.cpp behavior.

A migration marked `safe: true` means the individual replacement is known to preserve semantics. The fixer may still refuse to apply it when the surrounding command makes the migration ambiguous.

Every new migration or conflict rule should include a regression test when practical.

## Parser changes

Parser changes should prefer false negatives over false positives. `llama-doctor` should not reject a valid llama.cpp command merely because the help output is ambiguous.

Add a fixture or focused unit test for every parser bug fix.

## Pull requests

Before opening a pull request, run:

```bash
python -m compileall -q src tests
python -m pytest -q
```
