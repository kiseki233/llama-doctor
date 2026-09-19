# Project status

## Current version

`0.3.2.10731` — the version tracks the llama.cpp release used as ground truth
(`0.3.0-dev`, build 10731). Other builds are supported; the schema is read from
the selected executable.

## Implemented

- Runtime probing via `--version` and `--help`
- Dynamic flag schema extraction
- Correct handling of llama.cpp's wide-spaced alias rows
- Alias mapping
- Required, optional, enum-valued, and explicit numeric-range option parsing
- Enum extraction from braces, pipe lists, indented help bullets, and `allowed values:` lines
- Conservative primitive type inference
- CMD, Bash, and PowerShell multiline command handling
- Quoted Unicode path handling
- Unterminated-quote detection
- Unknown flag detection with close-match suggestions
- Missing and unexpected value detection
- Removed legacy migration flags are errors until successfully migrated
- Fix output is re-validated before the CLI reports success
- Basic integer/float/enum validation
- Positive/negative switch separation and conflict detection
- Duplicate and alias-duplicate detection
- Executable mismatch warning
- Environment-variable overlap info when exposed by help text
- Dynamic `(DEPRECATED)` marker detection
- Small migration/conflict rule system with upstream source provenance
- Deprecated rule reporting even when a legacy build still accepts the flag
- Safe command rewriting and alias normalization
- Ambiguous migration protection
- Local parsed-schema cache with corrupt/empty-cache fallback and schema-format invalidation
- JSON diagnostics and stable exit codes
- Stdin command input
- `probe` CLI command
- Typer/Rich CLI
- English / Simplified Chinese / Japanese CLI output via `--lang`
- Minimal PySide6 GUI source
- Runtime GUI language switcher for English / 简体中文 / 日本語
- Persisted GUI language preference with system-language fallback
- GUI executable-path/schema invalidation
- Windows PyInstaller build script
- Cross-platform GitHub Actions test workflow

## Verified

- Core Python modules compile successfully.
- 91 automated tests pass.
- Help parser regression tests use llama.cpp-style alias spacing and multiline enum descriptions.
- Cache hit and corrupt-cache fallback are tested without depending on a real llama.cpp binary.
- CLI has been exercised end-to-end against a fake llama-server executable that implements `--version` and `--help`.
- JSON diagnostics, normalization, migration fixing, and exit-code behavior are exercised.

## Verified against a real build (0.3.0.10731)

- Probed a real `llama-server` (`0.3.0-dev`, build 10731) on Windows: 287 flags
  parsed from its `--help`.
- Every parsed flag was submitted to that binary and its verdict compared with
  the linter's: **0 false positives**. The 18 remaining disagreements are all
  value-*format* rules the binary enforces and this project deliberately does
  not model (device specifiers, `fname:scale` pairs, directory existence).
- The PySide6 GUI was launched and driven end to end. Probe, Analyze, Fix and
  Normalize produce the same diagnostics as the CLI.
- A PyInstaller console executable was built and run. The packaged
  `rules/*.json` resolve correctly from the frozen bundle.

## Verified for the localization (0.3.2.10731)

- The GUI language selector was exercised on Windows with PySide6 6.11.2:
  switching relabels the open window, diagnostics re-render in the selected
  language while their `code` values stay fixed, and the choice is written to
  `QSettings` and read back on the next start.
- CLI output in English, Simplified Chinese and Japanese was checked against a
  real `llama-server`, not only the test double. All three report the same
  diagnostic codes and the same error and warning counts.
- The repository was cloned fresh from its remote and the whole suite run from
  that clone.

## Not verified

- The GUI `.exe` produced by `scripts/build_windows.ps1` has not been built;
  only the console build was exercised.
- Only one llama.cpp build has been used as ground truth. Help-text parsing may
  differ on older releases or on builds from other toolchains.

Use `scripts/build_windows.ps1` on Windows to create executable builds.
