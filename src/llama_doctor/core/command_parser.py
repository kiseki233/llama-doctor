from __future__ import annotations

from dataclasses import dataclass

from .models import BuildSchema, CommandArgument, ParsedCommand


class CommandParseError(ValueError):
    pass


@dataclass(slots=True)
class _Token:
    value: str
    quoted: bool = False


def _join_multiline(text: str) -> str:
    """Remove explicit line continuations while preserving quoted newlines.

    Quote state is tracked across lines so a caret/backslash/backtick that is
    part of a multiline quoted value is never mistaken for a shell continuation.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    out: list[str] = []
    quote: str | None = None
    token_started = False
    i = 0

    while i < len(text):
        ch = text[i]

        if quote == "'":
            out.append(ch)
            if ch == "'":
                quote = None
            i += 1
            continue

        if quote == '"':
            out.append(ch)
            if ch == '"':
                backslashes = 0
                j = i - 1
                while j >= 0 and text[j] == "\\":
                    backslashes += 1
                    j -= 1
                if backslashes % 2 == 0:
                    quote = None
            i += 1
            continue

        if ch in {"^", "\\", "`"} and i + 1 < len(text) and text[i + 1] == "\n":
            run = 1
            j = i - 1
            while j >= 0 and text[j] == ch:
                run += 1
                j -= 1
            if run % 2 == 1:
                out.append(" ")
                token_started = False
                i += 2
                continue

        if ch == '"':
            quote = ch
            token_started = True
            out.append(ch)
        elif ch == "'":
            if not token_started or (out and out[-1] == "="):
                quote = ch
            token_started = True
            out.append(ch)
        else:
            out.append(ch)
            if ch.isspace():
                token_started = False
            else:
                token_started = True
        i += 1

    return "".join(out)


def _tokenize_with_metadata(text: str) -> list[_Token]:
    text = _join_multiline(text.strip())
    tokens: list[_Token] = []
    buf: list[str] = []
    quote: str | None = None
    token_started = False
    token_quoted = False
    i = 0

    def finish_token() -> None:
        nonlocal buf, token_started, token_quoted
        if token_started:
            tokens.append(_Token("".join(buf), quoted=token_quoted))
        buf = []
        token_started = False
        token_quoted = False

    while i < len(text):
        ch = text[i]

        if quote == "'":
            if ch == "'":
                quote = None
            else:
                buf.append(ch)
            token_started = True
            i += 1
            continue

        if quote == '"':
            if ch == "\\":
                # Match the common Windows argv rule for backslashes before a
                # quote, while leaving ordinary path backslashes untouched.
                start = i
                while i < len(text) and text[i] == "\\":
                    i += 1
                count = i - start
                if i < len(text) and text[i] == '"':
                    buf.extend("\\" * (count // 2))
                    if count % 2:
                        buf.append('"')
                    else:
                        quote = None
                    token_started = True
                    i += 1
                    continue
                buf.extend("\\" * count)
                token_started = True
                continue
            if ch == '"':
                quote = None
            else:
                buf.append(ch)
            token_started = True
            i += 1
            continue

        if ch == '"':
            if not token_started:
                token_quoted = True
            quote = ch
            token_started = True
        elif ch == "'":
            # Single quotes are common shell quoting on Bash/PowerShell, but
            # apostrophes are also valid literal characters in Windows paths.
            # Treat them as a quote delimiter at token start or directly after
            # an '=' assignment; otherwise preserve the apostrophe literally.
            if not token_started or (buf and buf[-1] == "="):
                if not token_started:
                    token_quoted = True
                quote = ch
                token_started = True
            else:
                buf.append(ch)
                token_started = True
        elif ch.isspace():
            finish_token()
        elif ch in {"^", "`"} and i + 1 < len(text):
            # CMD caret / PowerShell backtick escapes outside quotes.
            i += 1
            buf.append(text[i])
            token_started = True
        else:
            buf.append(ch)
            token_started = True
        i += 1

    if quote:
        raise CommandParseError(f"Unterminated {quote} quote in command.")

    finish_token()
    return tokens


def tokenize_command(text: str) -> list[str]:
    """Tokenize common CMD/PowerShell/Bash-style llama.cpp commands.

    This intentionally does not execute or expand shell syntax. It supports
    single/double quotes, common CMD/PowerShell escapes, and multiline
    continuation with ``^``, ``\\`` or backtick.
    """
    return [token.value for token in _tokenize_with_metadata(text)]


def _looks_like_flag(token: str) -> bool:
    if not token.startswith("-") or token in {"-", "--"}:
        return False
    # Negative numeric values should remain values, not flags.
    try:
        float(token)
        return False
    except ValueError:
        return True


def parse_command(text: str, schema: BuildSchema | None = None) -> ParsedCommand:
    meta_tokens = _tokenize_with_metadata(text)
    tokens = [token.value for token in meta_tokens]
    executable: str | None = None
    start = 0

    if tokens and not _looks_like_flag(tokens[0]):
        executable = tokens[0]
        start = 1

    alias_map = schema.alias_map() if schema else {}
    args: list[CommandArgument] = []
    extras: list[tuple[int, str]] = []
    i = start

    while i < len(meta_tokens):
        token_meta = meta_tokens[i]
        token = token_meta.value
        if not _looks_like_flag(token) or token_meta.quoted:
            # Keep it, positioned after the arguments parsed so far, so that a
            # rewritten command still contains everything the user typed.
            extras.append((len(args), token))
            i += 1
            continue

        raw_flag = token
        inline_value: str | None = None
        if "=" in token:
            candidate_flag, candidate_value = token.split("=", 1)
            if _looks_like_flag(candidate_flag):
                raw_flag, inline_value = candidate_flag, candidate_value

        canonical = alias_map.get(raw_flag)
        definition = schema.flags.get(canonical) if schema and canonical else None
        value = inline_value

        if value is None:
            expects_value = definition.takes_value if definition else False
            if expects_value and i + 1 < len(meta_tokens):
                nxt = meta_tokens[i + 1]
                next_canonical = alias_map.get(nxt.value) if schema else None
                required_text_value = bool(
                    definition
                    and definition.requires_value
                    and definition.value_type in {None, "string", "path"}
                )
                if (
                    nxt.quoted
                    or not _looks_like_flag(nxt.value)
                    or (required_text_value and next_canonical is None)
                ):
                    value = nxt.value
                    i += 1
            elif not definition and i + 1 < len(meta_tokens):
                # Unknown flags: consume an obvious non-flag value to preserve intent.
                nxt = meta_tokens[i + 1]
                if nxt.quoted or not _looks_like_flag(nxt.value):
                    value = nxt.value
                    i += 1

        args.append(
            CommandArgument(
                raw_flag=raw_flag,
                canonical_flag=canonical,
                value=value,
                position=len(args),
            )
        )
        i += 1

    return ParsedCommand(
        executable=executable,
        arguments=args,
        raw_tokens=tokens,
        source=text,
        extras=extras,
    )
