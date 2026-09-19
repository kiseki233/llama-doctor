from pathlib import Path

from llama_doctor.core.command_parser import parse_command
from llama_doctor.core.fixer import fix_command
from llama_doctor.core.help_parser import parse_help
from llama_doctor.core.normalizer import normalize_command
from llama_doctor.core.rules import MigrationRule


def schema():
    text = (Path(__file__).parent / "fixtures" / "help_server.txt").read_text()
    return parse_help(text, "llama-server", "test")


def test_normalize_aliases():
    s = schema()
    parsed = parse_command('llama-server -m "model name.gguf" -c 4096', s)
    assert normalize_command(parsed, s) == 'llama-server --model "model name.gguf" --ctx-size 4096'


def test_safe_migration():
    s = schema()
    parsed = parse_command("llama-server --old", s)
    rules = {"--old": MigrationRule("r", "--old", "--load-mode none", True, "")}
    fixed = fix_command(parsed, s, rules)
    assert fixed.command == "llama-server --load-mode none"
    assert fixed.applied


def test_multiple_legacy_flags_collapsing_to_same_target_require_review():
    s = schema()
    parsed = parse_command("llama-server --old-a --old-b", s)
    rules = {
        "--old-a": MigrationRule("a", "--old-a", "--load-mode none", True, ""),
        "--old-b": MigrationRule("b", "--old-b", "--load-mode mlock", True, ""),
    }
    fixed = fix_command(parsed, s, rules)
    assert fixed.command == "llama-server --old-a --old-b"
    assert not fixed.applied
    assert len(fixed.review_required) == 2


def test_legacy_flag_is_not_auto_applied_when_new_target_already_present():
    s = schema()
    parsed = parse_command("llama-server --old --load-mode mmap", s)
    rules = {"--old": MigrationRule("r", "--old", "--load-mode none", True, "")}
    fixed = fix_command(parsed, s, rules)
    assert "--old" in fixed.command
    assert fixed.review_required


def test_normalizer_preserves_negative_toggle_semantics():
    text = (Path(__file__).parent / "fixtures" / "help_real_style.txt").read_text()
    s = parse_help(text, "llama-server", "test")
    parsed = parse_command("llama-server -nkvo --no-perf", s)
    normalized = normalize_command(parsed, s)
    assert normalized == "llama-server --no-kv-offload --no-perf"


def test_normalizer_round_trips_quoted_directory_with_trailing_backslash():
    s = schema()
    parsed = parse_command('llama-server -m "C:\\Model Dir\\\\"', s)
    normalized = normalize_command(parsed, s)
    reparsed = parse_command(normalized, s)
    assert reparsed.arguments[0].value == 'C:\\Model Dir\\'


def test_normalizer_round_trips_embedded_quote():
    text = (Path(__file__).parent / "fixtures" / "help_server.txt").read_text()
    text += '\n--prompt PROMPT                       prompt text\n'
    s = parse_help(text, "llama-server", "test")
    parsed = parse_command('llama-server --prompt "say \\"hi\\""', s)
    normalized = normalize_command(parsed, s)
    reparsed = parse_command(normalized, s)
    assert reparsed.arguments[0].value == 'say "hi"'


def test_normalizer_preserves_flag_looking_string_value():
    text = (Path(__file__).parent / "fixtures" / "help_server.txt").read_text()
    text += '\n--prompt PROMPT                       prompt text\n'
    s = parse_help(text, "llama-server", "test")
    parsed = parse_command('llama-server --prompt "--ctx-size" -c 4096', s)
    normalized = normalize_command(parsed, s)
    assert '"--ctx-size"' in normalized
    reparsed = parse_command(normalized, s)
    assert reparsed.arguments[0].value == "--ctx-size"
    assert reparsed.arguments[1].raw_flag == "--ctx-size"


def test_normalizer_quotes_common_shell_metacharacters():
    text = (Path(__file__).parent / "fixtures" / "help_server.txt").read_text()
    text += '\n--prompt PROMPT                       prompt text\n'
    s = parse_help(text, "llama-server", "test")
    parsed = parse_command('llama-server --prompt "a&b"', s)
    normalized = normalize_command(parsed, s)
    assert '"a&b"' in normalized
    assert parse_command(normalized, s).arguments[0].value == "a&b"


def test_fix_keeps_tokens_that_belong_to_no_flag():
    """A rewritten command must not be shorter than the one handed in.

    Bare words were skipped while parsing and never re-emitted, so
    ``llama-server -m m.gguf --threads 4 leftover`` came back without
    ``leftover``: fix silently shortened the user's command.
    """
    s = schema()
    parsed = parse_command("llama-server -m model.gguf --threads 4 leftover", s)
    result = fix_command(parsed, s, {})
    assert result.command.endswith("leftover")
    for token in parsed.raw_tokens[1:]:
        assert token in result.command


def test_stray_token_keeps_its_place_between_flags():
    s = schema()
    parsed = parse_command("llama-server -m model.gguf stray --ctx-size 4096", s)
    assert normalize_command(parsed, s) == (
        "llama-server --model model.gguf stray --ctx-size 4096"
    )


def test_normalize_keeps_bare_separator_unquoted():
    s = schema()
    parsed = parse_command("llama-server -m model.gguf -- trailing", s)
    normalized = normalize_command(parsed, s)
    assert " -- " in normalized
    assert normalized.endswith("trailing")
