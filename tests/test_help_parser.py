from pathlib import Path

from llama_doctor.core.help_parser import parse_help


def test_help_parser_extracts_flags_and_aliases():
    text = (Path(__file__).parent / "fixtures" / "help_server.txt").read_text()
    schema = parse_help(text, "llama-server", "test-build")
    assert "--model" in schema.flags
    assert "-m" in schema.flags["--model"].aliases
    assert schema.flags["--model"].requires_value
    assert schema.flags["--ctx-size"].value_type == "integer"
    assert schema.flags["--flash-attn"].requires_value is False
    assert schema.flags["--flash-attn"].value_optional is True
    assert schema.flags["--flash-attn"].choices == ["on", "off", "auto"]
    assert schema.flags["--flash-attn"].env_var == "LLAMA_ARG_FLASH_ATTN"


def test_real_llama_help_spacing_preserves_all_aliases():
    text = (Path(__file__).parent / "fixtures" / "help_real_style.txt").read_text()
    schema = parse_help(text, "llama-server", "real-style")
    assert len(schema.flags) >= 16
    assert schema.alias_map()["-h"] == "--help"
    assert schema.alias_map()["--usage"] == "--help"
    assert schema.alias_map()["-t"] == "--threads"
    assert schema.alias_map()["-tb"] == "--threads-batch"
    assert schema.flags["--threads"].env_var == "LLAMA_ARG_THREADS"


def test_multiline_enum_bullets_become_choices():
    text = (Path(__file__).parent / "fixtures" / "help_real_style.txt").read_text()
    schema = parse_help(text, "llama-server", "real-style")
    load_mode = schema.flags["--load-mode"]
    assert load_mode.choices == ["none", "mmap", "mlock", "mmap+mlock", "dio"]
    assert load_mode.env_var == "LLAMA_ARG_LOAD_MODE"


def test_composite_value_syntax_is_not_overtyped():
    text = (Path(__file__).parent / "fixtures" / "help_real_style.txt").read_text()
    schema = parse_help(text, "llama-server", "real-style")
    assert schema.flags["--tensor-split"].value_type == "string"


def test_value_with_internal_hyphen_does_not_create_fake_flag():
    text = (Path(__file__).parent / "fixtures" / "help_real_style.txt").read_text()
    schema = parse_help(text, "llama-server", "real-style")
    assert "-hi" not in schema.alias_map()
    assert schema.flags["--cpu-range"].value_name == "lo-hi"


def test_positive_negative_toggles_are_not_collapsed_as_aliases():
    text = (Path(__file__).parent / "fixtures" / "help_real_style.txt").read_text()
    schema = parse_help(text, "llama-server", "real-style")
    aliases = schema.alias_map()
    assert aliases["--perf"] == "--perf"
    assert aliases["--no-perf"] == "--no-perf"
    assert aliases["-kvo"] == "--kv-offload"
    assert aliases["-nkvo"] == "--no-kv-offload"


def test_brace_enum_and_allowed_values_are_extracted():
    text = (Path(__file__).parent / "fixtures" / "help_real_style.txt").read_text()
    schema = parse_help(text, "llama-server", "real-style")
    assert schema.flags["--rope-scaling"].choices == ["none", "linear", "yarn"]
    assert schema.flags["--cache-type-k"].choices == ["f32", "f16", "bf16", "q8_0", "q4_0", "q4_1", "iq4_nl"]


def test_numeric_range_and_dynamic_deprecation_are_extracted():
    text = (Path(__file__).parent / "fixtures" / "help_real_style.txt").read_text()
    schema = parse_help(text, "llama-server", "real-style")
    poll = schema.flags["--poll"]
    assert poll.value_type == "integer"
    assert poll.min_value == 0
    assert poll.max_value == 100
    assert schema.flags["--defrag-thold"].deprecated is True


def test_generic_n_is_not_assumed_integer_when_description_is_float_like():
    text = (Path(__file__).parent / "fixtures" / "help_real_style.txt").read_text()
    schema = parse_help(text, "llama-server", "real-style")
    assert schema.flags["--defrag-thold"].value_type == "float"
    assert schema.flags["--rope-scale"].value_type == "float"


def test_current_ctx_size_wording_is_inferred_as_integer():
    schema = parse_help(
        "-c, --ctx-size N                     size of the prompt context (default: 0)\n",
        "llama-server",
        "current",
    )
    assert schema.flags["--ctx-size"].value_type == "integer"


def test_current_alias_ordering_for_gpu_layers_and_negative_repack_switch():
    schema = parse_help(
        "-ngl, --gpu-layers, --n-gpu-layers N   max. number of layers to store in VRAM, either an exact number, 'auto', or 'all'\n"
        "--repack, -nr, --no-repack              whether to enable weight repacking\n",
        "llama-server",
        "current",
    )
    aliases = schema.alias_map()
    assert aliases["-ngl"] == aliases["--n-gpu-layers"] == "--gpu-layers"
    assert aliases["-nr"] == "--no-repack"
    assert aliases["--repack"] == "--repack"


def test_flag_name_with_interior_dot_is_parsed():
    """llama.cpp ships --fim-qwen-1.5b-default next to its dotless siblings.

    The flag-name pattern used to stop at the dot and then fail its own
    lookahead, so the whole option row was dropped and a valid command was
    reported as an unknown flag.
    """
    schema = parse_help(
        "--fim-qwen-1.5b-default                 use default Qwen 2.5 Coder 1.5B\n"
        "--fim-qwen-3b-default                   use default Qwen 2.5 Coder 3B\n",
        "llama-server",
        "current",
    )
    assert "--fim-qwen-1.5b-default" in schema.flags
    assert "--fim-qwen-3b-default" in schema.flags


def test_trailing_period_after_flag_is_not_part_of_the_name():
    schema = parse_help(
        "--alpha VALUE                           see --beta. it is related\n",
        "llama-server",
        "current",
    )
    assert "--alpha" in schema.flags
    assert not any(name.endswith(".") for name in schema.flags)


def test_removed_argument_is_marked_and_keeps_its_replacement():
    """llama.cpp keeps removed options in --help so the error can explain itself.

    The row parses like any other flag, so without reading the wording the
    linter accepts a command the binary rejects at startup.
    """
    schema = parse_help(
        "--draft, --draft-n, --draft-max N       the argument has been removed. use --spec-draft-n-max or\n"
        "                                        --spec-draft-n-min instead\n",
        "llama-server",
        "current",
    )
    definition = schema.flags["--draft"]
    assert definition.removed is True
    assert definition.removal_hint == "--spec-draft-n-max"


def test_wildcard_family_in_help_does_not_create_a_flag():
    schema = parse_help(
        "--spec-ngram-size-m N                   the argument has been removed. use the respective\n"
        "                                        --spec-ngram-*-size-m\n",
        "llama-server",
        "current",
    )
    assert "-size-m" not in schema.flags
    assert "--spec-ngram-size-m" in schema.flags
    # No usable replacement can be named, so none is invented.
    assert schema.flags["--spec-ngram-size-m"].removal_hint is None
