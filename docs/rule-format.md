# Rule format

## Migration rules

Migration rules live in `src/llama_doctor/rules/migrations.json`.

```json
{
  "rules": [
    {
      "id": "unique-rule-id",
      "old_flag": "--old-flag",
      "replacement": "--new-flag value",
      "safe": false,
      "note": "Why this migration exists.",
      "source": "https://github.com/..."
    }
  ]
}
```

Only mark `safe` as `true` when the individual replacement is known to preserve intended semantics.

`safe: true` is not unconditional permission to rewrite. The fixer also checks command context. If multiple old flags map to the same new flag, or that new flag is already present, automatic application is blocked and manual review is requested.

## Conflict rules

Conflict rules live in `src/llama_doctor/rules/conflicts.json`.

```json
{
  "rules": [
    {
      "id": "unique-conflict-id",
      "flags": ["--old-a", "--new-a"],
      "severity": "warning",
      "note": "Why this combination needs attention.",
      "source": "https://github.com/..."
    }
  ]
}
```

Use conflict rules only for behavior that is documented or independently verified. Do not use them as a performance-tuning database.

When possible, include an upstream issue, discussion, changelog, pull request, or source-code reference in `source`.
