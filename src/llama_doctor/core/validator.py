from __future__ import annotations

from collections import defaultdict
from difflib import get_close_matches
from pathlib import Path, PureWindowsPath
from typing import Mapping

from . import diagnostics as codes
from .models import BuildSchema, Diagnostic, ParsedCommand, ValidationResult
from .rules import ConflictRule, MigrationRule


def _valid_type(value: str, value_type: str | None) -> bool:
    if value_type in (None, "string", "path"):
        return True
    if value_type == "integer":
        try:
            int(value, 10)
            return True
        except ValueError:
            return False
    if value_type == "float":
        try:
            float(value)
            return True
        except ValueError:
            return False
    return True


def _numeric_value(value: str, value_type: str | None) -> float | None:
    try:
        if value_type == "integer":
            return float(int(value, 10))
        if value_type == "float":
            return float(value)
    except ValueError:
        return None
    return None


def _portable_stem(value: str) -> str:
    normalized = value.strip().strip('"').strip("'")
    if "\\" in normalized:
        return PureWindowsPath(normalized).stem.lower()
    return Path(normalized).stem.lower()


def _unknown_suggestion(flag: str, alias_map: Mapping[str, str]) -> str | None:
    candidates = get_close_matches(flag, list(alias_map), n=1, cutoff=0.68)
    if not candidates:
        return None
    return alias_map[candidates[0]]


def _inverse_positive(flag: str) -> str | None:
    if flag.startswith("--no-"):
        return "--" + flag[5:]
    return None


def validate_command(
    parsed: ParsedCommand,
    schema: BuildSchema,
    migrations: dict[str, MigrationRule] | None = None,
    conflicts: list[ConflictRule] | None = None,
    selected_executable: str | None = None,
    environment: Mapping[str, str] | None = None,
) -> ValidationResult:
    migrations = migrations or {}
    conflicts = conflicts or []
    diagnostics: list[Diagnostic] = []
    alias_map = schema.alias_map()

    if not parsed.raw_tokens:
        return ValidationResult([Diagnostic(severity="error", code=codes.EMPTY_COMMAND, message="Command is empty.")])

    if parsed.executable and selected_executable:
        command_name = _portable_stem(parsed.executable)
        selected_name = _portable_stem(selected_executable)
        if command_name != selected_name:
            diagnostics.append(
                Diagnostic(
                    severity="warning",
                    code=codes.EXECUTABLE_MISMATCH,
                    message=f"Command names {parsed.executable}, but validation uses {selected_executable}.",
                    suggestion="Validation is based on the selected executable.",
                )
            )

    seen: dict[str, list[tuple[str, int]]] = defaultdict(list)
    present_canonical: set[str] = set()
    present_raw: set[str] = set()

    for arg in parsed.arguments:
        present_raw.add(arg.raw_flag)
        canonical = alias_map.get(arg.raw_flag)
        arg.canonical_flag = canonical
        migration = migrations.get(arg.raw_flag)
        migration_reported = False

        if migration:
            replacement_flag = migration.replacement.split(maxsplit=1)[0]
            target_available = replacement_flag in alias_map
            if canonical and target_available:
                diagnostics.append(
                    Diagnostic(
                        severity="warning",
                        code=codes.DEPRECATED_FLAG,
                        flag=arg.raw_flag,
                        value=arg.value,
                        message=migration.note or "Deprecated or migrated flag.",
                        suggestion=migration.replacement,
                        source=migration.source or None,
                        safe_fix=migration.safe,
                        position=arg.position,
                    )
                )
                migration_reported = True
            elif not canonical and target_available:
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        code=codes.MIGRATION_REQUIRED,
                        flag=arg.raw_flag,
                        value=arg.value,
                        message=(
                            f"{arg.raw_flag} is not supported by this build and must be migrated. "
                            + (migration.note or "")
                        ).strip(),
                        suggestion=migration.replacement,
                        source=migration.source or None,
                        safe_fix=migration.safe,
                        position=arg.position,
                    )
                )
                migration_reported = True
            elif not canonical:
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        code=codes.MIGRATION_TARGET_UNAVAILABLE,
                        flag=arg.raw_flag,
                        value=arg.value,
                        message=(
                            f"{arg.raw_flag} is not supported by this build, and known migration target "
                            f"{replacement_flag} is unavailable too."
                        ),
                        source=migration.source or None,
                        position=arg.position,
                    )
                )
                migration_reported = True

        if not canonical:
            if not migration:
                suggestion = _unknown_suggestion(arg.raw_flag, alias_map)
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        code=codes.UNKNOWN_FLAG,
                        flag=arg.raw_flag,
                        value=arg.value,
                        message=f"{arg.raw_flag} is not supported by this build.",
                        suggestion=suggestion,
                        position=arg.position,
                    )
                )
            continue

        present_canonical.add(canonical)
        seen[canonical].append((arg.raw_flag, arg.position))
        definition = schema.flags[canonical]

        if definition.removed and not migration_reported:
            # The build lists the flag but rejects it at runtime, so this is an
            # error even though the flag is present in the schema.
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code=codes.REMOVED_FLAG,
                    flag=arg.raw_flag,
                    value=arg.value,
                    message=f"{arg.raw_flag} has been removed in this build and will be rejected at runtime.",
                    suggestion=definition.removal_hint,
                    position=arg.position,
                )
            )
        elif definition.deprecated and not migration_reported:
            diagnostics.append(
                Diagnostic(
                    severity="warning",
                    code=codes.DEPRECATED_FLAG,
                    flag=arg.raw_flag,
                    value=arg.value,
                    message=f"{arg.raw_flag} is marked deprecated by this build's --help output.",
                    position=arg.position,
                )
            )

        if definition.requires_value and arg.value is None:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code=codes.MISSING_VALUE,
                    flag=arg.raw_flag,
                    message=f"Missing value for {arg.raw_flag}.",
                    position=arg.position,
                )
            )
            continue

        if arg.value is not None and not definition.takes_value:
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code=codes.UNEXPECTED_VALUE,
                    flag=arg.raw_flag,
                    value=arg.value,
                    message=f"{arg.raw_flag} does not accept a value in this build.",
                    position=arg.position,
                )
            )
            continue

        if arg.value is not None and definition.takes_value:
            type_ok = _valid_type(arg.value, definition.value_type)
            if definition.choices:
                choice_ok = arg.value in definition.choices
                if definition.value_type in {"integer", "float"}:
                    value_ok = choice_ok or type_ok
                    expected = f"{definition.value_type} or one of {', '.join(definition.choices)}"
                else:
                    value_ok = choice_ok
                    expected = f"one of {', '.join(definition.choices)}"
            else:
                value_ok = type_ok
                expected = definition.value_type or "valid"

            if not value_ok:
                diagnostics.append(
                    Diagnostic(
                        severity="error",
                        code=codes.INVALID_VALUE,
                        flag=arg.raw_flag,
                        value=arg.value,
                        message=f"Expected {expected} value, received {arg.value!r}.",
                        position=arg.position,
                    )
                )
            else:
                numeric = _numeric_value(arg.value, definition.value_type)
                if numeric is not None:
                    below = definition.min_value is not None and numeric < definition.min_value
                    above = definition.max_value is not None and numeric > definition.max_value
                    if below or above:
                        diagnostics.append(
                            Diagnostic(
                                severity="error",
                                code=codes.INVALID_RANGE,
                                flag=arg.raw_flag,
                                value=arg.value,
                                message=(
                                    f"Value {arg.value!r} is outside the supported range "
                                    f"{definition.min_value:g}...{definition.max_value:g}."
                                ),
                                position=arg.position,
                            )
                        )

    if environment is not None:
        for canonical in sorted(present_canonical):
            definition = schema.flags[canonical]
            if definition.env_var and definition.env_var in environment:
                diagnostics.append(
                    Diagnostic(
                        severity="info",
                        code=codes.ENV_OVERRIDE,
                        flag=canonical,
                        message=f"CLI value overrides environment variable {definition.env_var}.",
                    )
                )

    for canonical, uses in seen.items():
        if len(uses) > 1:
            distinct = {use[0] for use in uses}
            diagnostics.append(
                Diagnostic(
                    severity="warning",
                    code=codes.ALIAS_DUPLICATE if len(distinct) > 1 else codes.DUPLICATE_FLAG,
                    flag=canonical,
                    message=(
                        f"{canonical} appears {len(uses)} times through aliases: {', '.join(sorted(distinct))}."
                        if len(distinct) > 1
                        else f"{canonical} appears {len(uses)} times."
                    ),
                    safe_fix=False,
                )
            )

    # Dynamically detect positive/negative toggle pairs parsed from a single help
    # row. These are semantic opposites, not aliases.
    dynamic_conflicts: set[tuple[str, str]] = set()
    for canonical in present_canonical:
        positive = _inverse_positive(canonical)
        if positive and positive in present_canonical:
            pair = (positive, canonical)
            if pair not in dynamic_conflicts:
                dynamic_conflicts.add(pair)
                diagnostics.append(
                    Diagnostic(
                        severity="warning",
                        code=codes.CONFLICTING_FLAGS,
                        flag=f"{positive}, {canonical}",
                        message=f"Both {positive} and {canonical} are present; effective behavior is order-dependent.",
                    )
                )

    for rule in conflicts:
        normalized = [alias_map.get(flag, flag) for flag in rule.flags]
        if all(flag in present_canonical or flag in present_raw for flag in normalized):
            diagnostics.append(
                Diagnostic(
                    severity=rule.severity if rule.severity in {"error", "warning", "info"} else "warning",
                    code=codes.CONFLICTING_FLAGS,
                    flag=", ".join(rule.flags),
                    message=rule.note or f"Conflicting flags: {', '.join(rule.flags)}",
                    source=rule.source or None,
                )
            )

    if not diagnostics:
        diagnostics.append(Diagnostic(severity="ok", code="OK", message="No problems found."))

    return ValidationResult(diagnostics)
