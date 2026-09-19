# Changelog

## 0.3.2.10731

Found by exercising the 0.3.1 localization on Windows with PySide6 installed,
which the environment it was written in did not have.

- Fixed two Japanese strings that made different things read identically. 解析
  ("parse") was used for both the Probe and the Analyze button, leaving the GUI
  with two buttons that read the same, and a failed probe and a failed command
  parse both reported 解析に失敗, so the message could not say which had
  happened. Probe is now プローブ.
- Added a check that no two keys describing different things collapse onto the
  same text in any language; the intended synonyms are listed explicitly, so a
  new collision has to be looked at rather than slipping past a heuristic.
- `*.egg-info/` is ignored. An editable install left build metadata in the tree.
- Automated coverage is now 91 tests.
- The verified llama.cpp baseline is unchanged: `0.3.0-dev`, build `10731`.

### Verified in this release

- The GUI language selector: switching relabels the open window, diagnostics
  re-render in the new language while their `code` values stay fixed, and the
  choice survives a restart via `QSettings`.
- CLI output in all three languages against a real `llama-server`
  (`0.3.0-dev`, build 10731) rather than only the test double.

## 0.3.1.10731

- Added runtime English / Simplified Chinese / Japanese localization.
- Added a GUI language selector; the selected language is persisted with QSettings.
- GUI startup language follows the system language when no saved preference exists.
- Added `--lang en|zh|ja` to CLI commands while keeping English as the backward-compatible default.
- Localized CLI tables, status text, diagnostic presentation, version/probe output, and common probe/parse errors.
- JSON diagnostics can be localized while stable diagnostic `code` values remain language-independent.
- Added English, Simplified Chinese, and Japanese README files.
- Added multilingual regression tests; automated coverage is now 89 tests.
- The verified llama.cpp baseline is unchanged: `0.3.0-dev`, build `10731`.

## 0.3.0.10731

Versioning changed: the number now names the llama.cpp release this build was
verified against, `<upstream version>.<upstream build>`. llama.cpp tags its
releases by build number, so `10731` is the identifier its users recognise.
This release is the former `0.1.3`; the tool still reads the flag schema from
whichever executable is selected and is not restricted to that build.

- `llama-doctor version` reports both the tool version and the verified
  llama.cpp version and build, with `--json` for scripts.
- `probe` notes when the selected build is newer or older than the verified
  one, and stays quiet when they match.

Everything below was found by running the linter against that real build and
comparing its verdict, flag by flag, with what the binary itself accepts. That
sweep now reports **0 false positives across 287 flags**.

- Fixed flag names containing a dot being dropped from the schema entirely. The
  name pattern stopped at the dot and then failed its own lookahead, so
  `--fim-qwen-1.5b-default` was reported as an unknown flag while its dotless
  siblings parsed fine -- a valid command diagnosed as broken.
- Fixed wildcard families in help text creating phantom flags. "use the
  respective `--spec-ngram-*-size-m`" contributed `-size-m` and `-min-hits` to
  the schema, so the linter accepted two flags the binary rejects.
- Added detection of arguments that `--help` still lists but the build refuses
  at runtime ("the argument has been removed. use ..."). These are now a
  `REMOVED_FLAG` error carrying the replacement named by the help text, instead
  of passing as ordinary flags. Covers `--draft`, `--draft-min`,
  `--spec-ngram-size-n`, `--spec-ngram-size-m` and `--spec-ngram-min-hits`.
- Fixed `fix` and `normalize` silently dropping tokens that belong to no flag.
  `llama-cli -m m.gguf -p hello world` came back without `world`: the rewritten
  command was shorter than the one the user pasted. Stray tokens now keep their
  original position.
- Stopped quoting a bare `--` separator in rewritten output.
- The schema cache key now includes a fingerprint of the `FlagDefinition`
  fields, so adding a field retires old entries automatically. A cache written
  between two of the changes above was still accepted and silently suppressed
  the new `REMOVED_FLAG` check.
- Coverage is now 80 tests.

### Verified in this release

- The PySide6 GUI was launched and driven end to end; its verdict matches the
  CLI diagnostic for diagnostic.
- A PyInstaller console build was produced and run, confirming the packaged
  `rules/*.json` are found from a frozen executable.

## 0.1.2

- Fixed removed-but-known migration flags being reported as warnings/valid commands. A removed legacy flag is now an error until migrated.
- `fix` now re-validates its generated command and returns exit code 1 when unknown flags, invalid values, or other errors remain.
- Added exit code 2 handling for internal CLI failures instead of leaking tracebacks in normal command paths.
- Fixed quoted empty values (`""`) being dropped by the command tokenizer.
- Fixed single-line Windows paths ending in `\` being mistaken for multiline continuations.
- Reworked quoted backslash/quote handling so normalized Windows paths and embedded quotes round-trip safely.
- Fixed `--flag="quoted value"` and `--flag='quoted value'` being skipped as if the whole token were a quoted positional value.
- Preserved quoted values that begin with `-`, and allowed required string/path values such as prompts to begin with a dash.
- Made apostrophes inside ordinary unquoted Windows paths literal instead of treating them as the start of a shell quote.
- Preserved literal newlines inside quoted values and made multiline continuation processing quote-state aware across lines.
- Added safer quoting for common shell metacharacters in normalized/fixed output.
- Fixed current llama.cpp wording (`size of the prompt context`) so `--ctx-size` is correctly inferred as an integer option.
- Added conservative integer inference for common `INDEX`, `SEED`, and `PORT` metavariables.
- Rejected structurally valid but empty schema caches and bumped the cache schema format to 3 after parser/type-inference changes.
- GUI Fix now reports remaining errors after safe rewrites instead of always presenting the pass as complete.
- Expanded automated coverage to 69 tests plus randomized quote/token round-trip checks and CLI end-to-end smoke tests.

## 0.1.1

- Reworked help parsing so llama.cpp's spaced alias format such as `-h,    --help, --usage` is parsed correctly.
- Split positive/negative switch pairs (for example `--perf` / `--no-perf`) into distinct semantic options so normalization cannot invert behavior.
- Added enum extraction from brace syntax, `allowed values:` lines, and indented bullets.
- Added explicit numeric range validation for help syntax such as `<0...100>`.
- Added dynamic `(DEPRECATED)` detection from the selected build's help output.
- Added upstream source provenance to migration/conflict rules and JSON diagnostics.
- Versioned the schema cache so parser changes automatically invalidate old cache data.
- Added enum choice extraction from indented help bullets, including `--load-mode`-style values.
- Made primitive type inference more conservative for composite/list syntaxes.
- Added PowerShell backtick multiline handling.
- Added short-option `-x=value` parsing.
- Added unterminated-quote detection instead of silently accepting malformed commands.
- Added empty-command and unexpected-inline-value diagnostics.
- Added close-match suggestions for unknown flags.
- Deprecated migration rules are now reported even when the selected older build still accepts the legacy flag.
- Automatic migration fixing now refuses ambiguous rewrites when multiple legacy flags collapse into one target option or when that target is already present.
- Added local parsed-schema caching with corruption fallback and `--no-cache`.
- Added `llama-doctor probe` and stdin input support.
- Fixed GUI schema invalidation when the selected executable path changes.
- Expanded automated coverage to 44 tests.

## 0.1.0

- First working MVP.
- Runtime `--version` / `--help` probing.
- Dynamic option schema extraction and alias mapping.
- Basic validation, normalization, migration rules, Typer CLI, PySide6 GUI source, tests, and Windows build script.
