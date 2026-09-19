from pathlib import Path

import pytest

from llama_doctor.core.command_parser import CommandParseError, parse_command, tokenize_command
from llama_doctor.core.help_parser import parse_help


def schema():
    text = (Path(__file__).parent / "fixtures" / "help_server.txt").read_text()
    return parse_help(text, "llama-server", "test")


def test_windows_multiline_and_unicode_path():
    command = '''llama-server.exe ^\n  -m "D:\\模型\\Qwen 3\\model.gguf" ^\n  -c 32768 ^\n  -ngl 99'''
    parsed = parse_command(command, schema())
    assert parsed.executable == "llama-server.exe"
    assert parsed.arguments[0].value == "D:\\模型\\Qwen 3\\model.gguf"
    assert parsed.arguments[1].value == "32768"
    assert parsed.arguments[2].canonical_flag == "--n-gpu-layers"


def test_bash_multiline():
    tokens = tokenize_command("./llama-server \\\n --model 'model name.gguf' \\\n --ctx-size 4096")
    assert tokens == ["./llama-server", "--model", "model name.gguf", "--ctx-size", "4096"]


def test_powershell_backtick_multiline():
    tokens = tokenize_command("llama-server.exe `\n --model 'model name.gguf' `\n --ctx-size 4096")
    assert tokens == ["llama-server.exe", "--model", "model name.gguf", "--ctx-size", "4096"]


def test_negative_number_is_value():
    text = (Path(__file__).parent / "fixtures" / "help_server.txt").read_text()
    s = parse_help(text, "llama-server", "test")
    parsed = parse_command("llama-server --threads -3", s)
    assert parsed.arguments[0].value == "-3"


def test_short_flag_equals_value():
    parsed = parse_command("llama-server -c=4096", schema())
    assert parsed.arguments[0].raw_flag == "-c"
    assert parsed.arguments[0].value == "4096"


def test_unterminated_quote_is_rejected():
    with pytest.raises(CommandParseError):
        tokenize_command('llama-server --model "broken path.gguf')


def test_empty_quoted_value_is_preserved():
    tokens = tokenize_command('llama-server --model ""')
    assert tokens == ["llama-server", "--model", ""]
    parsed = parse_command('llama-server --model ""', schema())
    assert parsed.arguments[0].value == ""


def test_single_line_trailing_backslash_is_not_eaten():
    tokens = tokenize_command('llama-server --model C:\\models\\')
    assert tokens[-1] == 'C:\\models\\'


def test_quoted_flag_looking_value_is_consumed_as_value():
    s = schema()
    text = (Path(__file__).parent / "fixtures" / "help_server.txt").read_text()
    text += '\n--prompt PROMPT                       prompt text\n'
    s = parse_help(text, "llama-server", "test")
    parsed = parse_command('llama-server --prompt "--ctx-size" -c 4096', s)
    assert parsed.arguments[0].raw_flag == "--prompt"
    assert parsed.arguments[0].value == "--ctx-size"
    assert parsed.arguments[1].raw_flag == "-c"


def test_apostrophe_inside_unquoted_windows_value_is_literal():
    tokens = tokenize_command(r"llama-server --model D:\\Bob's\\model.gguf")
    assert tokens[-1] == r"D:\\Bob's\\model.gguf"


def test_single_quote_still_works_at_value_start_and_after_equals():
    assert tokenize_command("llama-server --model 'model name.gguf'")[-1] == "model name.gguf"
    assert tokenize_command("llama-server --model='model name.gguf'")[-1] == "--model=model name.gguf"


def test_cmd_multiline_with_apostrophe_in_path_still_continues():
    tokens = tokenize_command("llama-server.exe ^\n --model D:\\Bob's\\model.gguf ^\n -c 4096")
    assert tokens == ["llama-server.exe", "--model", "D:\\Bob's\\model.gguf", "-c", "4096"]


def test_inline_equals_with_quoted_value_is_still_a_flag():
    s = schema()
    parsed = parse_command(r'llama-server --model="C:\\Model Dir\\model.gguf" -c 4096', s)
    assert parsed.arguments[0].raw_flag == "--model"
    assert parsed.arguments[0].value == r"C:\\Model Dir\\model.gguf"
    assert parsed.arguments[1].raw_flag == "-c"


def test_inline_equals_with_single_quoted_value_is_still_a_flag():
    s = schema()
    parsed = parse_command("llama-server --model='model name.gguf' -c 4096", s)
    assert parsed.arguments[0].raw_flag == "--model"
    assert parsed.arguments[0].value == "model name.gguf"


def test_required_string_value_can_begin_with_dash():
    text = (Path(__file__).parent / "fixtures" / "help_server.txt").read_text()
    text += '\n--prompt PROMPT                       prompt text\n'
    s = parse_help(text, "llama-server", "test")
    parsed = parse_command("llama-server --prompt -hello -c 4096", s)
    assert parsed.arguments[0].raw_flag == "--prompt"
    assert parsed.arguments[0].value == "-hello"
    assert parsed.arguments[1].raw_flag == "-c"


def test_required_string_does_not_swallow_known_next_flag_unquoted():
    text = (Path(__file__).parent / "fixtures" / "help_server.txt").read_text()
    text += '\n--prompt PROMPT                       prompt text\n'
    s = parse_help(text, "llama-server", "test")
    parsed = parse_command("llama-server --prompt -c 4096", s)
    assert parsed.arguments[0].raw_flag == "--prompt"
    assert parsed.arguments[0].value is None
    assert parsed.arguments[1].raw_flag == "-c"


def test_literal_newline_inside_quoted_value_is_preserved():
    text = (Path(__file__).parent / "fixtures" / "help_server.txt").read_text()
    text += '\n--prompt PROMPT                       prompt text\n'
    s = parse_help(text, "llama-server", "test")
    parsed = parse_command('llama-server --prompt "line one\nline two" -c 4096', s)
    assert parsed.arguments[0].value == "line one\nline two"
    assert parsed.arguments[1].raw_flag == "-c"
