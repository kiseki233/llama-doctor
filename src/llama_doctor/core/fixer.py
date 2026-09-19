from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .models import BuildSchema, ParsedCommand
from .normalizer import emit_extras, quote_value
from .rules import MigrationRule


@dataclass(slots=True)
class FixResult:
    command: str
    applied: list[str]
    review_required: list[str]


def _replacement_tokens(replacement: str) -> tuple[str, str | None]:
    parts = replacement.split(maxsplit=1)
    if len(parts) == 1:
        return parts[0], None
    return parts[0], parts[1]


def fix_command(
    parsed: ParsedCommand,
    schema: BuildSchema,
    migrations: dict[str, MigrationRule] | None = None,
    normalize_aliases: bool = True,
) -> FixResult:
    migrations = migrations or {}
    alias_map = schema.alias_map()
    parts: list[str] = []
    applied: list[str] = []
    review_required: list[str] = []

    if parsed.executable:
        parts.append(quote_value(parsed.executable))

    # Migration rules can be individually correct but unsafe in combination.
    # Example: several legacy mmap/mlock flags all collapse into one --load-mode
    # option, where argument order changes semantics. Never auto-rewrite those
    # ambiguous combinations.
    migration_targets: dict[str, list[str]] = defaultdict(list)
    existing_canonical = {alias_map.get(arg.raw_flag, arg.raw_flag) for arg in parsed.arguments}
    for arg in parsed.arguments:
        rule = migrations.get(arg.raw_flag)
        if not rule:
            continue
        target, _ = _replacement_tokens(rule.replacement)
        if target in alias_map:
            migration_targets[target].append(arg.raw_flag)

    blocked_targets: set[str] = set()
    for target, sources in migration_targets.items():
        if len(sources) > 1 or target in existing_canonical:
            blocked_targets.add(target)

    for index, arg in enumerate(parsed.arguments):
        parts.extend(emit_extras(parsed, index))
        flag = arg.raw_flag
        value = arg.value
        rule = migrations.get(flag)

        if rule:
            new_flag, replacement_value = _replacement_tokens(rule.replacement)
            target_available = new_flag in alias_map
            if new_flag in blocked_targets:
                review_required.append(
                    f"{flag} -> {rule.replacement} (not auto-applied because multiple arguments affect {new_flag})"
                )
            elif rule.safe and target_available:
                applied.append(f"{flag} -> {rule.replacement}")
                flag = new_flag
                if replacement_value is not None:
                    value = replacement_value
            else:
                review_required.append(f"{flag} -> {rule.replacement}")
        elif normalize_aliases:
            flag = alias_map.get(flag, flag)

        parts.append(flag)
        if value is not None:
            parts.append(quote_value(value))

    parts.extend(emit_extras(parsed, len(parsed.arguments)))
    return FixResult(command=" ".join(parts), applied=applied, review_required=review_required)
