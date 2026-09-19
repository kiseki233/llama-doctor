# llama-doctor

[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

**Lint, diagnose and migrate llama.cpp commands against your installed build.**

`llama-doctor` probes the exact `llama-server` or `llama-cli` executable you select, parses its `--help` output, and validates a command against that build.

The project is intentionally narrow: it is a **command linter and migration assistant**, not a model launcher or optimizer.

## Languages

The desktop GUI supports **English, Simplified Chinese, and Japanese** with an in-app language selector. The GUI starts from the system language when possible and remembers the selected language.

CLI output can be selected per command:

```bash
llama-doctor check --lang en ...
llama-doctor check --lang zh ...
llama-doctor check --lang ja ...
```

English remains the CLI default for backward compatibility. Diagnostic `code` values stay language-independent, so scripts can safely rely on codes such as `UNKNOWN_FLAG` and `MISSING_VALUE`.

## Versions and compatibility

The version number names the llama.cpp release this build was verified against:

```text
llama-doctor  0.3.2.10731
                ^     ^
                |     llama.cpp build number
                llama.cpp version baseline
```

This does **not** mean other builds are unsupported. The flag schema is read from whichever executable you select. The trailing build number records the verified llama.cpp baseline.

For this release, the baseline remains `llama.cpp 0.3.0-dev (build 10731)`.

## What it does

- Probes the selected executable with `--version` and `--help`
- Builds a flag schema from that exact llama.cpp build
- Handles spaced aliases such as `-h,    --help, --usage`
- Handles required, optional, enum-valued, explicit numeric-range, and basic numeric options
- Handles common CMD, PowerShell, and Bash multiline command forms
- Handles quoted Unicode paths
- Detects unknown flags and suggests close matches
- Detects missing and unexpected values
- Detects basic integer/float/enum value errors
- Distinguishes true aliases from positive/negative switch pairs
- Detects duplicate flags, alias duplicates, and switch conflicts
- Warns when the command names a different executable than the selected build
- Reports environment-variable overlap when exposed by llama.cpp help
- Detects `(DEPRECATED)` markers directly from help output
- Reports known deprecated/migrated flags
- Extracts enum choices from multiple llama.cpp help formats
- Treats removed legacy flags as errors until migrated
- Applies only explicitly safe migrations
- Refuses ambiguous automatic migrations
- Re-validates fixed commands before reporting success
- Normalizes aliases to canonical long options
- Emits JSON diagnostics and stable exit codes
- Caches parsed executable schemas locally
- Includes a Typer/Rich CLI and a PySide6 GUI
- Supports English, Simplified Chinese, and Japanese presentation layers

## Deliberate non-goals

No model downloading, model management, chat UI, benchmarking, VRAM optimization, or automatic performance tuning.

`doctor != optimizer`.

## Install for development

```bash
python -m venv .venv
.venv/Scripts/activate  # Windows
pip install -e .

# Include the desktop GUI
pip install -e ".[gui]"
```

Linux/macOS activation:

```bash
source .venv/bin/activate
```

## CLI

Check a command:

```bash
llama-doctor check --exe "C:\AI\llama.cpp\llama-server.exe" "llama-server.exe -m model.gguf -c 32768"
```

Chinese output:

```bash
llama-doctor check --lang zh --exe ./llama-server "./llama-server -m model.gguf -c 32768"
```

Japanese output:

```bash
llama-doctor check --lang ja --exe ./llama-server "./llama-server -m model.gguf -c 32768"
```

Read from stdin:

```bash
echo "./llama-server -m model.gguf -c 32768" | llama-doctor check --exe ./llama-server -
```

JSON diagnostics:

```bash
llama-doctor check --json --lang zh --exe ./llama-server "./llama-server -m model.gguf -c 32768"
```

Inspect schema:

```bash
llama-doctor probe --exe ./llama-server
llama-doctor probe --json --exe ./llama-server
```

Normalize aliases:

```bash
llama-doctor normalize --exe ./llama-server "./llama-server -m model.gguf -c 32768"
```

Apply safe migrations:

```bash
llama-doctor fix --exe ./llama-server "./llama-server --no-mmap -m model.gguf"
```

Force a fresh probe:

```bash
llama-doctor check --no-cache --exe ./llama-server "./llama-server -m model.gguf"
```

### Exit codes

| Code | Meaning |
| ---: | --- |
| `0` | no validation errors |
| `1` | validation/parse error, unresolved fix, or manual review required |
| `2` | internal llama-doctor error |
| `3` | executable probing failed |

## GUI

```bash
pip install -e ".[gui]"
llama-doctor-gui
```

Workflow:

1. Choose English, 中文, or 日本語.
2. Select `llama-server` or `llama-cli`.
3. Probe the executable.
4. Paste a command.
5. Click **Analyze**.
6. Review diagnostics.
7. Use **Fix Command** or **Normalize** when appropriate.

## How it works

The selected executable's own `--help` output is the primary source of truth. `llama-doctor` does not ship a permanently complete llama.cpp argument database.

A small static rules directory is used only for facts that cannot be inferred reliably from `--help`, such as known migrations and unsafe legacy combinations.

Parsed schemas are cached using the executable path, size, and modification time. Set `LLAMA_DOCTOR_CACHE_DIR` to override the cache location.

## Migration safety

A rule can be marked safe, but `llama-doctor` still refuses to auto-apply it when the full command makes the rewrite ambiguous.

Several legacy mmap/mlock flags can collapse into the modern `--load-mode` option. If multiple legacy arguments affect the same target, the tool leaves them unchanged and reports **Review required** instead of guessing.

## Tests

```bash
python -m pytest -q
```

The multilingual release contains **91 tests**. It includes the existing parser/validator/cache coverage plus language normalization, translated diagnostic output, localized JSON, and Chinese/Japanese CLI checks.

## Windows executables

```powershell
./scripts/build_windows.ps1
```

Build output is written to `dist/`. Tagged GitHub pushes (`v*`) run the included release workflow.

## Important limitations

- Shell parsing is conservative and does not fully emulate CMD, PowerShell, or Bash.
- The current release validates one pasted llama.cpp command.
- Type inference from `--help` is deliberately conservative.
- Migration rules should only be added when upstream behavior is documented or verified.
- The GUI runtime requires the optional PySide6 dependency.

## Privacy

Validation is local. `llama-doctor` does not upload commands or models and does not require network access.

## License

MIT
