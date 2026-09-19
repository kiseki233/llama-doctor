# llama-doctor v0.1.2 Bug Audit

## Result

The v0.1.1 codebase was reviewed with unit tests, direct source inspection, parser round-trip fuzzing, CLI end-to-end smoke tests, and a built-wheel installation smoke test.

Several real defects were found and fixed. The corrected baseline is **v0.1.2**.

## Confirmed bugs fixed

### High — Removed migration flags could be reported as valid

A legacy flag present in `migrations.json` but absent from the selected build schema was previously treated as a warning. This could make `check` return exit code 0 even though the actual llama.cpp build would reject the command.

Fix:

- Added `MIGRATION_REQUIRED` as an error when the old flag is removed and the replacement exists.
- `MIGRATION_TARGET_UNAVAILABLE` is now an error when neither the old flag nor its known replacement is available.
- A legacy flag that is still accepted by the selected build remains a warning rather than an error.

### High — `fix` could return success while the command was still invalid

`fix` previously only checked whether a migration required manual review. Unknown flags, invalid values, and missing values could remain in the output while the command still exited successfully.

Fix:

- The generated command is parsed and validated again after safe fixes.
- `fix` returns exit code 1 if validation errors remain.
- GUI Fix also reports remaining errors.

### High — `--flag="quoted value"` could disappear from parsing

Quote metadata was too broad: a token containing a quoted value could be mistaken for a token that was entirely quoted, causing common forms such as `--model="C:\\Model Dir\\model.gguf"` to be skipped.

Fix:

- Quote metadata now records whether the token *began* quoted, rather than whether it contained any quoted section.
- Both double-quoted and single-quoted inline assignment forms have regression tests.

### High — Current `--ctx-size` wording could bypass integer validation

Current llama.cpp help describes the flag as `size of the prompt context`. Earlier inference only recognized wording such as `context size`, so a real build could accept `--ctx-size banana` in the linter.

Fix:

- Added the current wording to conservative integer inference.
- Added conservative `INDEX`, `SEED`, and `PORT` integer metavariable handling.
- Cache schema format was bumped so stale type inference is not reused after upgrade.

### Medium — Empty quoted values were dropped

`""` produced no token because the tokenizer only emitted a token when its character buffer was non-empty.

Fix:

- Token start state is tracked independently from buffer length.
- Empty quoted values now round-trip correctly.

### Medium — Windows directories ending in `\\` could be corrupted

A final backslash could be mistaken for a multiline continuation, and quoted trailing backslashes could interact incorrectly with the closing quote.

Fix:

- A continuation marker is only removed when it actually precedes another line and is outside quotes.
- Backslashes immediately before a closing quote use Windows-compatible escaping rules.
- Ordinary path backslashes remain untouched.

### Medium — Quoted values beginning with `-` could be changed into flags after normalization

Example: `--prompt "--ctx-size"` could normalize to `--prompt --ctx-size`, changing the meaning on a second parse.

Fix:

- Flag-looking string values are kept quoted.
- Required string/path values can consume unknown dash-prefixed values such as `-hello`.
- Known next flags are still treated as likely separate options when unquoted.

### Medium — Apostrophes in Windows paths could be swallowed

A literal apostrophe inside an unquoted Windows path could be treated as the start of a Bash/PowerShell single-quoted string.

Fix:

- Single quotes start shell-style quoting only at token start or directly after `=`.
- Mid-token apostrophes are preserved literally.

### Medium — Multiline quoted prompts could be modified

The old multiline preprocessor flattened all lines and could mistake a continuation marker inside a quoted multiline value for shell syntax.

Fix:

- Multiline processing now keeps quote state across lines.
- Only explicit continuation markers outside quotes are removed.
- Literal newlines inside quoted values are preserved.

### Medium — Structurally valid but empty schema cache could poison validation

A JSON cache with the right format but no flags was trusted, causing every real option to become unknown.

Fix:

- Empty cached schemas are rejected and re-probed.
- Schema cache format is now version 3.

### Low — Internal CLI failures had no stable exit code

Unexpected internal errors could leak normal Python failure behavior instead of following the documented CLI contract.

Fix:

- Exit code 2 is now used for internal llama-doctor failures.
- Probe failures remain exit code 3.

## Verification performed

- **69 automated tests pass**.
- Python `compileall` passes for source and tests.
- **10,000 randomized quote/token round-trip cases** passed after parser fixes.
- CLI was exercised end-to-end with an executable that really responds to `--version` and `--help`.
- The v0.1.2 wheel was built and inspected to confirm rule JSON files are included.
- The built wheel was installed into an isolated target directory and smoke-tested:
  - `version` reports `0.1.2`.
  - invalid `--ctx-size` returns a validation failure.
  - removed `--no-mmap` is safely rewritten to `--load-mode none` when supported.

## Remaining unverified areas

These are not known bugs, but they still need real-platform verification:

- The PySide6 GUI has not been launched in this environment because PySide6 is unavailable here.
- Native Windows PyInstaller `.exe` output has not been built or executed in this Linux environment.
- Shell parsing is intentionally conservative and is not a complete CMD, PowerShell, or Bash interpreter.
- Arbitrary multi-command `.bat`, `.ps1`, and `.sh` script extraction is still outside v0.1.x scope.

## Recommended next validation

Before a public GitHub release, run on Windows 11 with a current official llama.cpp build:

1. Launch the PySide6 GUI.
2. Probe real `llama-server.exe` and `llama-cli.exe`.
3. Paste several real commands copied from current llama.cpp documentation.
4. Build both PyInstaller executables with `scripts/build_windows.ps1`.
5. Run the packaged EXEs on a clean Windows machine or Windows Sandbox.
