from pathlib import Path

from typer.testing import CliRunner

from llama_doctor import cli
from llama_doctor.core.help_parser import parse_help
from llama_doctor.core.models import Diagnostic, ValidationResult
from llama_doctor.i18n import (
    diagnostic_message,
    normalize_language,
    tr,
    validation_to_dict,
)


runner = CliRunner()


def schema():
    text = (Path(__file__).parent / "fixtures" / "help_server.txt").read_text()
    return parse_help(text, "llama-server", "test-build")


def test_language_normalization():
    assert normalize_language("zh-CN") == "zh"
    assert normalize_language("ja-JP") == "ja"
    assert normalize_language("en-US") == "en"
    assert normalize_language("unknown") == "en"


def test_translation_basic_keys():
    assert tr("gui_analyze", "zh") == "分析"
    assert tr("gui_analyze", "ja") == "解析"
    assert tr("gui_analyze", "en") == "Analyze"


def test_diagnostic_translation_keeps_code_and_flag_semantics():
    diagnostic = Diagnostic(
        severity="error",
        code="UNKNOWN_FLAG",
        flag="--ctx-sze",
        message="Unknown flag --ctx-sze.",
        suggestion="--ctx-size",
    )
    assert "--ctx-sze" in diagnostic_message(diagnostic, "zh")
    assert "--ctx-sze" in diagnostic_message(diagnostic, "ja")


def test_json_localization_preserves_stable_diagnostic_code():
    result = ValidationResult(
        [Diagnostic(severity="error", code="MISSING_VALUE", flag="--ctx-size", message="Missing value")]
    )
    payload = validation_to_dict(result, "zh")
    assert payload["language"] == "zh"
    assert payload["diagnostics"][0]["code"] == "MISSING_VALUE"
    assert "缺少值" in payload["diagnostics"][0]["message"]


def test_cli_version_chinese():
    result = runner.invoke(cli.app, ["version", "--lang", "zh"])
    assert result.exit_code == 0
    assert "验证基线" in result.stdout


def test_cli_version_japanese():
    result = runner.invoke(cli.app, ["version", "--lang", "ja"])
    assert result.exit_code == 0
    assert "検証基準" in result.stdout


def test_cli_check_chinese_json(monkeypatch, tmp_path):
    exe = tmp_path / "llama-server"
    exe.write_text("fake")
    monkeypatch.setattr(cli, "probe_executable", lambda *args, **kwargs: schema())
    result = runner.invoke(
        cli.app,
        ["check", "--lang", "zh", "--json", "--exe", str(exe), "llama-server --ctx-sze 1"],
    )
    assert result.exit_code == 1
    assert '"language": "zh"' in result.stdout
    assert '"code": "UNKNOWN_FLAG"' in result.stdout
    assert "当前 build 不支持参数" in result.stdout


def test_cli_check_japanese_text(monkeypatch, tmp_path):
    exe = tmp_path / "llama-server"
    exe.write_text("fake")
    monkeypatch.setattr(cli, "probe_executable", lambda *args, **kwargs: schema())
    result = runner.invoke(
        cli.app,
        ["check", "--lang", "ja", "--exe", str(exe), "llama-server --ctx-sze 1"],
    )
    assert result.exit_code == 1
    assert "診断結果" in result.stdout
    assert "サポートしていません" in result.stdout


def test_cli_default_remains_english_for_backward_compatibility():
    result = runner.invoke(cli.app, ["version"])
    assert result.exit_code == 0
    assert "Verified against" in result.stdout


def test_distinct_actions_do_not_share_a_label_in_any_language():
    """Two controls that do different things must not read the same.

    Japanese used 解析 (parse) for both Probe and Analyze, leaving the GUI with
    two identically labelled buttons, and reported a failed probe and a failed
    parse with the same sentence.
    """
    from llama_doctor.i18n import _TRANSLATIONS

    # Keys that say the same thing in different places. They are listed rather
    # than matched by prefix so that a new collision has to be looked at and
    # added deliberately instead of slipping past a heuristic.
    SYNONYMS = frozenset(
        {
            frozenset({"gui_probe_failed", "cli_probe_failed"}),
            frozenset({"gui_applied_fixes", "cli_applied_fixes"}),
            frozenset({"gui_review_required", "cli_review_required"}),
            frozenset({"suggested", "cli_suggestion"}),
        }
    )

    def allowed(first: str, second: str) -> bool:
        pair = frozenset({first, second})
        return any(pair <= group for group in SYNONYMS)

    for language in ("en", "zh", "ja"):
        seen: dict[str, str] = {}
        for key, entry in _TRANSLATIONS.items():
            text = entry.get(language)
            if not text:
                continue
            previous = seen.get(text)
            if previous is not None and not allowed(previous, key):
                raise AssertionError(
                    f"{language}: {previous!r} and {key!r} both render as {text!r}"
                )
            seen.setdefault(text, key)


def test_every_key_is_translated_into_every_language():
    from llama_doctor.i18n import _TRANSLATIONS

    for key, entry in _TRANSLATIONS.items():
        for language in ("en", "zh", "ja"):
            assert entry.get(language), f"{key} is missing {language}"
