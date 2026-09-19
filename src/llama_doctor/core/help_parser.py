from __future__ import annotations

import re

from .models import BuildSchema, FlagDefinition

_ANGLE_VALUE = re.compile(r"<([^>]+)>")
_ENV = re.compile(r"\(env:\s*([A-Z0-9_]+)\)", re.IGNORECASE)
_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
# A dot can appear inside a flag name: llama.cpp ships --fim-qwen-1.5b-default
# next to --fim-qwen-3b-default. Only interior dots are accepted -- a dot must be
# followed by an alphanumeric -- so a flag that ends a sentence does not swallow
# the full stop.
# The lookbehind also rejects '*', because help text points at families of
# options with wildcards -- "use the respective --spec-ngram-*-size-m" -- and
# without it the tail '-size-m' was picked up as a flag of its own.
_FLAG_NAME = re.compile(
    r"(?<![A-Za-z0-9_./*])"
    r"(-{1,2}[A-Za-z0-9][A-Za-z0-9_-]*(?:\.[A-Za-z0-9][A-Za-z0-9_-]*)*)"
    r"(?=,|\s|$)"
)
_ENUM_BULLET = re.compile(r"^\s*-\s+([A-Za-z0-9_+./-]+)\s*:")
_ALLOWED_VALUES = re.compile(r"allowed values:\s*(.+)", re.IGNORECASE)
_REMOVED_PHRASE = re.compile(r"\b(?:argument|option|flag)\s+has\s+been\s+removed\b", re.IGNORECASE)
_NUMERIC_RANGE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\.\.\.?(-?\d+(?:\.\d+)?)\s*$")


def _infer_type(value_name: str | None, description: str) -> str | None:
    """Conservatively infer primitive value types from llama.cpp help text.

    llama.cpp often uses the metavariable ``N`` for both integer counts and
    floating-point tuning values, so the metavariable alone is not enough to
    reject user input. Description semantics are used only when reasonably
    explicit.
    """
    if not value_name:
        return None

    v = value_name.strip().lower()
    d = description.lower()

    range_match = _NUMERIC_RANGE.match(v)
    if range_match:
        return "float" if any("." in item for item in range_match.groups()) else "integer"

    # Composite/list/pattern syntaxes should not be forced into a primitive type.
    if any(marker in v for marker in (",", "=", ":", "/")):
        return "string"

    if v in {"f", "float", "ratio", "temp", "temperature", "prob", "probability"}:
        return "float"
    if v in {"file", "fname", "filename", "path", "dir", "directory", "model"}:
        return "path"

    normalized = re.sub(r"[^a-z0-9]+", " ", v).split()
    if any(token in {"path", "file", "fname", "filename", "dir", "directory"} for token in normalized):
        return "path"
    if any(token in {"float", "ratio", "temp", "temperature", "prob", "probability"} for token in normalized):
        return "float"

    # Float-like tuning semantics take precedence over generic N.
    if re.search(r"\b(factor|threshold|temperature|probability|penalty|frequency)\b", d):
        return "float"

    # Count/size semantics are generally integral in llama.cpp CLI options.
    if re.search(
        r"\b(integer|number of|count of|threads?|layers?|tokens?|sequences?|context size|"
        r"size of (?:the )?(?:prompt )?context|batch size|maximum batch size)\b",
        d,
    ):
        return "integer"

    if v in {
        "threads",
        "layers",
        "layer",
        "batch",
        "ctx",
        "context",
        "count",
        "size",
        "index",
        "seed",
        "port",
    }:
        return "integer"

    return "string"


def _split_option_and_description(line: str) -> tuple[str, str]:
    """Split a llama.cpp help row without confusing spaced aliases for columns."""
    stripped = line.strip()
    if not stripped:
        return "", ""

    for match in re.finditer(r"\s{2,}", stripped):
        left = stripped[: match.start()].rstrip()
        right = stripped[match.end() :].lstrip()
        if not right:
            continue
        if left.endswith(","):
            continue
        return left, right

    return stripped, ""


def _extract_value_syntax(
    option_text: str,
    names: list[str],
) -> tuple[str | None, bool, list[str] | None, float | None, float | None]:
    if not names:
        return None, False, None, None, None

    last = option_text.rfind(names[-1])
    after = option_text[last + len(names[-1]) :].strip(" ,")
    if not after:
        return None, False, None, None, None

    angle = _ANGLE_VALUE.search(after)
    raw_candidate = angle.group(0) if angle else after.split()[0]
    optional = raw_candidate.startswith("[") and raw_candidate.endswith("]")
    brace_enum = raw_candidate.startswith("{") and raw_candidate.endswith("}")
    candidate = raw_candidate.strip("[]<>{}")
    if not candidate or candidate.startswith("-"):
        return None, False, None, None, None

    choices: list[str] | None = None
    if "|" in candidate:
        choices = [item.strip() for item in candidate.split("|") if item.strip()]
    elif brace_enum and "," in candidate:
        choices = [item.strip() for item in candidate.split(",") if item.strip()]

    min_value: float | None = None
    max_value: float | None = None
    range_match = _NUMERIC_RANGE.match(candidate)
    if range_match:
        min_value = float(range_match.group(1))
        max_value = float(range_match.group(2))

    return candidate, optional, choices, min_value, max_value


def _partition_names(names: list[str]) -> list[tuple[str, list[str]]]:
    """Partition positive/negative toggle names into semantic definitions.

    llama.cpp prints pairs such as ``-kvo, --kv-offload, -nkvo,
    --no-kv-offload`` on one help row. The negative spelling is not a synonym of
    the positive spelling, so it must not be normalized to the positive option.
    """
    long_names = [name for name in names if name.startswith("--")]
    has_inverse_pair = any(
        name.startswith("--no-") and f"--{name[5:]}" in long_names
        for name in long_names
    )

    if not has_inverse_pair:
        canonical = long_names[0] if long_names else names[0]
        aliases = [name for name in names if name != canonical]
        return [(canonical, list(dict.fromkeys(aliases)))]

    groups: list[tuple[str, list[str]]] = []
    pending_short: list[str] = []
    positive_index: int | None = None

    for name in names:
        if not name.startswith("--"):
            pending_short.append(name)
            continue

        if name.startswith("--no-") and f"--{name[5:]}" in long_names:
            groups.append((name, list(dict.fromkeys(pending_short))))
            pending_short = []
            continue

        if positive_index is None:
            groups.append((name, list(dict.fromkeys(pending_short))))
            positive_index = len(groups) - 1
            pending_short = []
        else:
            canonical, aliases = groups[positive_index]
            aliases.extend(pending_short)
            aliases.append(name)
            groups[positive_index] = (canonical, list(dict.fromkeys(aliases)))
            pending_short = []

    if pending_short and positive_index is not None:
        canonical, aliases = groups[positive_index]
        aliases.extend(pending_short)
        groups[positive_index] = (canonical, list(dict.fromkeys(aliases)))

    return groups


def _make_definitions(option_text: str, description: str) -> list[FlagDefinition]:
    names = _FLAG_NAME.findall(option_text)
    if not names:
        return []

    value_name, value_optional, choices, min_value, max_value = _extract_value_syntax(option_text, names)
    if not choices and any(marker in description.lower() for marker in (" either ", " one of ", " or ")):
        quoted = re.findall(r"['\"]([A-Za-z0-9_+./-]+)['\"]", description)
        if quoted:
            choices = list(dict.fromkeys(quoted))

    env_match = _ENV.search(description)
    deprecated = "deprecated" in description.lower()
    removed, removal_hint = _detect_removal(description)
    definitions: list[FlagDefinition] = []

    for canonical, aliases in _partition_names(names):
        definition = FlagDefinition(
            name=canonical,
            aliases=aliases,
            requires_value=value_name is not None and not value_optional,
            value_optional=value_optional,
            value_name=value_name,
            value_type=_infer_type(value_name, description),
            choices=list(choices) if choices else None,
            min_value=min_value,
            max_value=max_value,
            env_var=env_match.group(1) if env_match else None,
            deprecated=deprecated,
            removed=removed,
            removal_hint=removal_hint,
            description=description.strip(),
        )
        _add_allowed_values(definition, description)
        definitions.append(definition)

    return definitions


def _detect_removal(description: str) -> tuple[bool, str | None]:
    """Spot flags that --help still lists but the build refuses at runtime.

    llama.cpp keeps removed options in the help output so that the error is
    explanatory: "--draft, --draft-n, --draft-max N  the argument has been
    removed. use --spec-draft-n-max or ...". Treating that as an ordinary flag
    lets a command through that the binary will reject, which is exactly the
    situation this tool exists to prevent.
    """
    if not _REMOVED_PHRASE.search(description):
        return False, None
    # Prefer the replacement the help text names, ignoring wildcard families
    # such as --spec-ngram-*-size-m, which are not usable as-is.
    hint = None
    tail = description[_REMOVED_PHRASE.search(description).end() :]
    for candidate in _FLAG_NAME.findall(tail):
        if "*" not in candidate:
            hint = candidate
            break
    return True, hint


def _merge_definition(existing: FlagDefinition, new: FlagDefinition) -> FlagDefinition:
    existing.aliases = list(dict.fromkeys(existing.aliases + new.aliases))
    if new.description:
        existing.description = (existing.description + " " + new.description).strip()
    existing.requires_value = existing.requires_value or new.requires_value
    existing.value_optional = existing.value_optional or new.value_optional
    existing.value_name = existing.value_name or new.value_name
    existing.value_type = existing.value_type or new.value_type
    existing.choices = existing.choices or new.choices
    existing.min_value = existing.min_value if existing.min_value is not None else new.min_value
    existing.max_value = existing.max_value if existing.max_value is not None else new.max_value
    existing.env_var = existing.env_var or new.env_var
    existing.deprecated = existing.deprecated or new.deprecated
    existing.removed = existing.removed or new.removed
    existing.removal_hint = existing.removal_hint or new.removal_hint
    return existing


def _add_allowed_values(definition: FlagDefinition, text: str) -> None:
    match = _ALLOWED_VALUES.search(text)
    if not match:
        return
    value_text = match.group(1).split("(", 1)[0]
    values = [item.strip().strip(". ;") for item in value_text.split(",")]
    values = [item for item in values if item and re.fullmatch(r"[A-Za-z0-9_+.-]+", item)]
    if not values:
        return
    if definition.choices is None:
        definition.choices = []
    for value in values:
        if value not in definition.choices:
            definition.choices.append(value)


def parse_help(help_text: str, executable_type: str = "unknown", version: str = "unknown") -> BuildSchema:
    help_text = _ANSI.sub("", help_text)
    flags: dict[str, FlagDefinition] = {}
    current: list[FlagDefinition] = []

    for raw in help_text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            current = []
            continue

        stripped = line.lstrip()
        begins_with_flag = bool(re.match(r"-{1,2}[A-Za-z0-9]", stripped))

        if begins_with_flag:
            option_text, description = _split_option_and_description(line)
            definitions = _make_definitions(option_text, description)
            if definitions:
                current = []
                for definition in definitions:
                    existing = flags.get(definition.name)
                    if existing:
                        definition = _merge_definition(existing, definition)
                    else:
                        flags[definition.name] = definition
                    current.append(definition)
                continue

        if current and line.startswith((" ", "\t")):
            extra = line.strip()
            if not extra:
                continue

            for definition in current:
                definition.description = (definition.description + " " + extra).strip()

                env_match = _ENV.search(extra)
                if env_match:
                    definition.env_var = env_match.group(1)

                if "deprecated" in extra.lower():
                    definition.deprecated = True

                bullet = _ENUM_BULLET.match(line)
                if bullet:
                    choice = bullet.group(1)
                    if definition.choices is None:
                        definition.choices = []
                    if choice not in definition.choices:
                        definition.choices.append(choice)

                _add_allowed_values(definition, extra)

    return BuildSchema(
        executable_type=executable_type,
        version=version,
        flags=flags,
        raw_help=help_text,
    )
