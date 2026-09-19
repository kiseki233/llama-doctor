from pathlib import Path

from llama_doctor.core.command_parser import parse_command
from llama_doctor.core.help_parser import parse_help
from llama_doctor.core.rules import MigrationRule
from llama_doctor.core.validator import validate_command


def schema():
    text = (Path(__file__).parent / "fixtures" / "help_server.txt").read_text()
    return parse_help(text, "llama-server", "test")


def real_schema():
    text = (Path(__file__).parent / "fixtures" / "help_real_style.txt").read_text()
    return parse_help(text, "llama-server", "test")


def codes(result):
    return {diagnostic.code for diagnostic in result.diagnostics}


def test_unknown_missing_invalid_and_duplicate():
    s = schema()
    parsed = parse_command("llama-server -c banana --ctx-size --mystery x", s)
    result = validate_command(parsed, s)
    assert "INVALID_VALUE" in codes(result)
    assert "MISSING_VALUE" in codes(result)
    assert "UNKNOWN_FLAG" in codes(result)
    assert "ALIAS_DUPLICATE" in codes(result)


def test_migration_is_reported_before_unknown():
    s = schema()
    parsed = parse_command("llama-server --old-flag", s)
    migrations = {
        "--old-flag": MigrationRule(
            id="test",
            old_flag="--old-flag",
            replacement="--load-mode none",
            safe=True,
            note="migrated",
        )
    }
    result = validate_command(parsed, s, migrations)
    assert "MIGRATION_REQUIRED" in codes(result)
    assert "UNKNOWN_FLAG" not in codes(result)
    assert not result.valid


def test_supported_but_deprecated_flag_still_warns():
    s = real_schema()
    migrations = {
        "--no-mmap": MigrationRule(
            id="test",
            old_flag="--no-mmap",
            replacement="--load-mode none",
            safe=True,
            note="deprecated",
        )
    }
    result = validate_command(parse_command("llama-server --no-mmap", s), s, migrations)
    assert "DEPRECATED_FLAG" in codes(result)
    assert "UNKNOWN_FLAG" not in codes(result)


def test_optional_choice_value():
    s = schema()
    ok = validate_command(parse_command("llama-server -fa on", s), s)
    assert "INVALID_VALUE" not in codes(ok)
    bad = validate_command(parse_command("llama-server -fa banana", s), s)
    assert "INVALID_VALUE" in codes(bad)


def test_integer_or_named_choice():
    s = schema()
    result = validate_command(parse_command("llama-server -ngl auto", s), s)
    assert "INVALID_VALUE" not in codes(result)
    result2 = validate_command(parse_command("llama-server -ngl all", s), s)
    assert "INVALID_VALUE" not in codes(result2)


def test_enum_bullets_validate_load_mode():
    s = real_schema()
    good = validate_command(parse_command("llama-server --load-mode mmap+mlock", s), s)
    bad = validate_command(parse_command("llama-server --load-mode magic", s), s)
    assert "INVALID_VALUE" not in codes(good)
    assert "INVALID_VALUE" in codes(bad)


def test_unknown_flag_gets_close_suggestion():
    s = schema()
    result = validate_command(parse_command("llama-server --ctx-sze 4096", s), s)
    diagnostic = next(item for item in result.diagnostics if item.code == "UNKNOWN_FLAG")
    assert diagnostic.suggestion == "--ctx-size"


def test_empty_command_is_error():
    result = validate_command(parse_command("", schema()), schema())
    assert "EMPTY_COMMAND" in codes(result)
    assert not result.valid


def test_inline_value_on_boolean_flag_is_error():
    s = real_schema()
    result = validate_command(parse_command("llama-server --mmap=true", s), s)
    assert "UNEXPECTED_VALUE" in codes(result)


def test_windows_executable_name_comparison_is_portable():
    s = schema()
    parsed = parse_command("llama-server.exe -c 4096", s)
    result = validate_command(parsed, s, selected_executable=r"C:\\AI\\llama-server.exe")
    assert "EXECUTABLE_MISMATCH" not in codes(result)


def test_positive_and_negative_switches_conflict_but_are_not_alias_duplicates():
    s = real_schema()
    result = validate_command(parse_command("llama-server --perf --no-perf", s), s)
    assert "CONFLICTING_FLAGS" in codes(result)
    assert "ALIAS_DUPLICATE" not in codes(result)


def test_allowed_values_from_help_are_validated():
    s = real_schema()
    good = validate_command(parse_command("llama-server --cache-type-k q8_0", s), s)
    bad = validate_command(parse_command("llama-server --cache-type-k banana", s), s)
    assert "INVALID_VALUE" not in codes(good)
    assert "INVALID_VALUE" in codes(bad)


def test_explicit_numeric_range_is_validated():
    s = real_schema()
    good = validate_command(parse_command("llama-server --poll 50", s), s)
    bad = validate_command(parse_command("llama-server --poll 101", s), s)
    assert "INVALID_RANGE" not in codes(good)
    assert "INVALID_RANGE" in codes(bad)


def test_deprecated_marker_from_help_is_reported_without_static_rule():
    s = real_schema()
    result = validate_command(parse_command("llama-server --defrag-thold 0.1", s), s)
    assert "DEPRECATED_FLAG" in codes(result)


def test_float_threshold_using_n_metavariable_is_not_rejected():
    s = real_schema()
    result = validate_command(parse_command("llama-server --defrag-thold 0.1", s), s)
    assert "INVALID_VALUE" not in codes(result)


def test_removed_migratable_flag_is_error_until_fixed():
    s = schema()
    parsed = parse_command("llama-server --old-flag", s)
    migrations = {
        "--old-flag": MigrationRule(
            id="test",
            old_flag="--old-flag",
            replacement="--load-mode none",
            safe=True,
            note="migrated",
        )
    }
    result = validate_command(parsed, s, migrations)
    diagnostic = next(item for item in result.diagnostics if item.code == "MIGRATION_REQUIRED")
    assert diagnostic.severity == "error"
    assert not result.valid


def test_removed_migratable_flag_with_missing_target_is_error():
    s = schema()
    parsed = parse_command("llama-server --old-flag", s)
    migrations = {
        "--old-flag": MigrationRule(
            id="test",
            old_flag="--old-flag",
            replacement="--future-flag none",
            safe=True,
            note="migrated",
        )
    }
    result = validate_command(parsed, s, migrations)
    diagnostic = next(item for item in result.diagnostics if item.code == "MIGRATION_TARGET_UNAVAILABLE")
    assert diagnostic.severity == "error"
    assert not result.valid


def test_current_ctx_size_wording_rejects_non_integer():
    s = parse_help(
        "-c, --ctx-size N                     size of the prompt context (default: 0)\n",
        "llama-server",
        "current",
    )
    result = validate_command(parse_command("llama-server -c banana", s), s)
    assert "INVALID_VALUE" in codes(result)
