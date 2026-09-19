# Multilingual status — 0.3.1.10731

## Added

- Runtime English / Simplified Chinese / Japanese localization layer.
- GUI language selector: `中文`, `日本語`, `English`.
- GUI language preference persistence via `QSettings`.
- First-run GUI language detection from the operating system locale.
- `--lang en|zh|ja` on CLI commands.
- Localized diagnostic tables, status text, common error text, probe/version output and JSON diagnostic messages.
- Stable diagnostic codes remain unchanged across languages.
- Full README files in English, Simplified Chinese, and Japanese.
- Source-distribution manifest now includes translated READMEs, docs, tests and fixtures.

## Verification

- Existing test suite remained green after localization.
- Added multilingual regression coverage.
- Final result: **89/89 tests passed**.
- Python source and tests pass `compileall`.
- Wheel built successfully.
- Wheel package contains `llama_doctor/i18n.py` and both rules JSON files.
- Installed-wheel smoke tests passed for `version --lang en`, `--lang zh`, and `--lang ja`.
- End-to-end CLI `check` output was exercised in all three languages against a fake llama-server implementing `--version` and `--help`.

## GUI verified separately

The localization work was done without PySide6 available, so the language
selector was checked afterwards on Windows with PySide6 6.11.2 installed:

- Switching between `中文`, `日本語` and `English` relabels the open window; no
  restart is needed.
- Diagnostics re-render in the selected language while the diagnostic `code`
  values stay unchanged.
- The choice is written to `QSettings` and read back on the next start.

That pass found two Japanese strings where different things read identically:
解析 ("parse") was used for both the Probe and the Analyze button, and a failed
probe and a failed command parse both produced 解析に失敗. Probe is now
プローブ, and a test rejects any such collision, with the intended synonyms
listed explicitly.

CLI output in all three languages was also exercised against a real
`llama-server` (`0.3.0-dev`, build 10731), not only the test double.

## Not runtime-verified

The `.exe` from `scripts/build_windows.ps1` has not been built for this release;
only the wheel and an editable install were exercised.

## Compatibility

The verified llama.cpp baseline is unchanged:

- llama.cpp version: `0.3.0-dev`
- llama.cpp build: `10731`

The project version is bumped from `0.3.0.10731` to `0.3.1.10731` to mark the multilingual feature update while retaining the same upstream verification baseline.
