# llama-doctor 0.3.0.10731 Bug Audit

## Method

Earlier audits reasoned about the code and exercised it against a fake
`llama-server` built for the tests. This one used the real thing as the oracle.

`llama-server` parses its arguments before it opens the model file, so pointing
it at a path that does not exist separates the two failure modes cleanly:

```text
valid flags   + missing model -> "gguf_init_from_file: failed to open GGUF file"
invalid flags + missing model -> "error: invalid argument: --totally-bogus-flag"
```

Every flag in the parsed schema was then submitted to the binary this way, and
its verdict compared with the linter's. Nothing was loaded onto the GPU and no
model was read.

The two directions are not equally serious. A **false positive** — the linter
rejecting a command the binary accepts — makes the tool actively harmful,
because it sends the user to fix something that was never broken. A **false
negative** only means the linter missed something, leaving the user no worse off
than without it.

## Result

| | before | after |
| --- | --- | --- |
| flags checked | 289 | 287 |
| false positives | 0 | **0** |
| false negatives | 25 | **18** |

The 18 remaining disagreements are all value-*format* rules the binary enforces
and this project deliberately does not model: device specifiers, `fname:scale`
pairs, JSON payloads, directory existence. They are consistent with the stated
scope of conservative primitive type inference, and are not counted as defects.

The flag count dropped by two because two of them never existed.

## Confirmed bugs fixed

### High — a dot in a flag name dropped the whole option

`--fim-qwen-1.5b-default` was reported as an unknown flag, while
`--fim-qwen-3b-default` and `--fim-qwen-7b-default` parsed normally.

The flag-name pattern allowed `[A-Za-z0-9_-]` only. On reaching the dot it
stopped, then failed its own `(?=,|\s|$)` lookahead, so the match failed
entirely and the option row was discarded rather than truncated. This is the
false-positive case: a valid command diagnosed as broken.

Fix: interior dots are accepted. A dot must be followed by an alphanumeric, so a
flag ending a sentence still does not swallow the full stop.

### High — wildcards in help text invented flags

llama.cpp points at families of options with a wildcard:

```text
--spec-ngram-size-m N    the argument has been removed. use the respective
                         --spec-ngram-*-size-m
```

The lookbehind excluded `[A-Za-z0-9_./]` but not `*`, so the tail `-size-m`
qualified as a flag of its own. `-size-m` and `-min-hits` entered the schema and
the linter accepted both; the binary rejects them with `invalid argument`.

Fix: `*` was added to the lookbehind.

### High — arguments the build refuses were treated as valid

llama.cpp keeps removed options in `--help` so that the failure can explain
itself:

```text
--draft, --draft-n, --draft-max N    the argument has been removed. use
                                     --spec-draft-n-max or --spec-draft-n-min
```

Only the `(DEPRECATED)` marker was recognised, so these rows parsed as ordinary
flags and the linter passed commands the binary rejects at startup. Migration
assistance is the point of the tool, which makes this the most costly of the
three.

Fix: the removal wording is detected, the flag is reported as `REMOVED_FLAG`
(error, not warning), and the replacement named in the help text is carried into
the diagnostic. Wildcard families are not offered as replacements, since they
cannot be used as written. Covers `--draft`, `--draft-min`,
`--spec-ngram-size-n`, `--spec-ngram-size-m` and `--spec-ngram-min-hits`.

### High — `fix` and `normalize` silently shortened the command

A token belonging to no flag was skipped during parsing and never recorded, and
both rewriters rebuild their output from the executable and the arguments. Any
bare word was therefore dropped:

```text
in   llama-cli -m model.gguf -p hello world
out  llama-cli --model model.gguf -p hello
```

The user's prompt came back a word shorter, with nothing reported. A tool that
hands back a modified command must not remove parts of it.

Fix: stray tokens are kept with the number of arguments that preceded them, and
re-emitted in that position. A bare `--` separator is also no longer quoted,
since the tokenizer does not treat it as a flag and quoting only obscured it.

### Medium — a stale schema cache silently disabled a new check

Introduced and caught during this audit. `SCHEMA_CACHE_FORMAT` was raised for
the parser changes, and `FlagDefinition` gained its `removed` field afterwards.
Entries written in between carried the current format number but not the new
field, so they loaded successfully with `removed=False` — and the new
`REMOVED_FLAG` check went quiet instead of failing loudly. The CLI reported
`--draft` correctly with `--no-cache` and missed it without.

Fix: the cache key and the cache file both carry a fingerprint of the
`FlagDefinition` field names. Adding a field now retires old entries on its own,
and the failure mode does not depend on remembering a manual bump.

## Previously unverified, now verified

- **PySide6 GUI.** Launched and driven end to end — set executable, Probe,
  Analyze, Fix Command, Normalize. Its diagnostics match the CLI's, code for
  code. An apparent disagreement during testing turned out to be the test
  harness writing the command into the read-only results pane.
- **Frozen executable.** A PyInstaller console build was produced and run
  against the real binary. The packaged `rules/*.json` resolve correctly from
  the bundle, which is the part most likely to break once frozen.
- **Wheel.** Built and installed into a clean virtual environment, then run
  against the real binary; all fixes are present in the packaged artifact.

## Still not verified

- The GUI `.exe` from `scripts/build_windows.ps1`; only the console build was
  produced.
- Any llama.cpp build other than `0.3.0-dev (build 10731)`. Help-text parsing is
  the part most exposed to upstream formatting changes, and one build is one
  data point.

## Coverage

80 tests, including regressions for each defect above: dotted flag names,
trailing periods, wildcard families, removal wording and its extracted
replacement, stray-token preservation, separator quoting, and the build-number
comparison shown by `probe`.
