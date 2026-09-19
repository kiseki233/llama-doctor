from __future__ import annotations

from .models import BuildSchema, ParsedCommand


def quote_value(value: str) -> str:
    """Quote one argv value using Windows-compatible double-quote escaping.

    The same representation also round-trips through llama-doctor's tokenizer.
    Ordinary backslashes are preserved; only runs before embedded/closing quotes
    need special handling.
    """
    shell_meta = set("&|<>^;()`")
    # "-" and "--" are not flags to the tokenizer, so they round-trip bare and
    # quoting them would only obscure a shell separator the user wrote.
    flag_like = value.startswith("-") and value not in {"-", "--"}
    if flag_like:
        try:
            float(value)
        except ValueError:
            pass
        else:
            flag_like = False

    if (
        value
        and not flag_like
        and not any(ch.isspace() for ch in value)
        and '"' not in value
        and not any(ch in shell_meta for ch in value)
    ):
        return value

    out: list[str] = ['"']
    backslashes = 0
    for ch in value:
        if ch == "\\":
            backslashes += 1
            continue
        if ch == '"':
            out.append("\\" * (backslashes * 2 + 1))
            out.append('"')
            backslashes = 0
            continue
        if backslashes:
            out.append("\\" * backslashes)
            backslashes = 0
        out.append(ch)

    # Backslashes immediately before the closing quote must be doubled.
    if backslashes:
        out.append("\\" * (backslashes * 2))
    out.append('"')
    return "".join(out)


def emit_extras(parsed: ParsedCommand, index: int) -> list[str]:
    """Return the stray tokens that sat after ``index`` arguments, re-quoted."""
    return [quote_value(token) for position, token in parsed.extras if position == index]


def normalize_command(parsed: ParsedCommand, schema: BuildSchema) -> str:
    alias_map = schema.alias_map()
    parts: list[str] = []
    if parsed.executable:
        parts.append(quote_value(parsed.executable))
    for index, arg in enumerate(parsed.arguments):
        parts.extend(emit_extras(parsed, index))
        canonical = alias_map.get(arg.raw_flag, arg.raw_flag)
        parts.append(canonical)
        if arg.value is not None:
            parts.append(quote_value(arg.value))
    parts.extend(emit_extras(parsed, len(parsed.arguments)))
    return " ".join(parts)
