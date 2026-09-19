# Architecture

`llama-doctor` is split into three layers:

1. **Probe/schema layer** — executes `--version` and `--help` on a selected llama.cpp executable, parses the output, and optionally caches the resulting build schema.
2. **Core analysis layer** — tokenizes commands, maps aliases, validates arguments, applies explicit migration/conflict rules, normalizes commands, and emits stable diagnostic codes.
3. **Frontends** — Typer CLI and PySide6 GUI. Both call the same core functions.

## Source of truth

The selected executable's own `--help` output is the primary source of truth. Static rules are intentionally limited to facts that cannot be inferred reliably from `--help`, such as documented migrations.

## Help parser strategy

The parser is deliberately tolerant of llama.cpp's human-formatted output. In particular, it does not use a naive two-space column split because aliases are themselves often separated by wide spacing:

```text
-h,    --help, --usage                  print usage and exit
```

It also collects enum candidates from indented bullet descriptions when possible.

## Validation strategy

Validation is conservative. If a value type cannot be inferred reliably, it remains a string rather than risking a false-positive rejection.

## Migration safety

Migration rules are context-checked before automatic rewriting. If multiple legacy flags map to the same modern target option, or the target is already present in the command, the fixer requires manual review instead of applying an order-dependent rewrite.

## Cache

Schemas are cached by executable path, file size, modification time, and an internal cache-format version. Parser/schema changes can therefore invalidate old caches automatically. Cache failures are non-fatal; probing always remains available as a fallback.
