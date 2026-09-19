from pathlib import Path

from typer.testing import CliRunner

from llama_doctor import VERIFIED_LLAMA_CPP_BUILD, __version__
from llama_doctor import cli
from llama_doctor.core.help_parser import parse_help


runner = CliRunner()


def schema():
    text = (Path(__file__).parent / "fixtures" / "help_server.txt").read_text()
    return parse_help(text, "llama-server", "test-build")


def test_version_command():
    result = runner.invoke(cli.app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_check_json_exit_code_and_suggestion(monkeypatch, tmp_path):
    exe = tmp_path / "llama-server"
    exe.write_text("fake")
    monkeypatch.setattr(cli, "probe_executable", lambda *args, **kwargs: schema())
    result = runner.invoke(
        cli.app,
        ["check", "--json", "--exe", str(exe), "llama-server --ctx-sze nope"],
    )
    assert result.exit_code == 1
    assert '"code": "UNKNOWN_FLAG"' in result.stdout
    assert '"suggestion": "--ctx-size"' in result.stdout


def test_check_parse_error_is_validation_failure(monkeypatch, tmp_path):
    exe = tmp_path / "llama-server"
    exe.write_text("fake")
    monkeypatch.setattr(cli, "probe_executable", lambda *args, **kwargs: schema())
    result = runner.invoke(
        cli.app,
        ["check", "--json", "--exe", str(exe), 'llama-server -m "broken'],
    )
    assert result.exit_code == 1
    assert '"code": "PARSE_ERROR"' in result.stdout


def test_fix_exits_nonzero_when_unresolved_error_remains(monkeypatch, tmp_path):
    exe = tmp_path / "llama-server"
    exe.write_text("fake")
    monkeypatch.setattr(cli, "probe_executable", lambda *args, **kwargs: schema())
    result = runner.invoke(
        cli.app,
        ["fix", "--exe", str(exe), "llama-server --mystery value"],
    )
    assert result.exit_code == 1
    assert "Remaining validation errors" in result.stdout


def test_fix_can_resolve_removed_safe_migration(monkeypatch, tmp_path):
    exe = tmp_path / "llama-server"
    exe.write_text("fake")
    monkeypatch.setattr(cli, "probe_executable", lambda *args, **kwargs: schema())
    monkeypatch.setattr(
        cli,
        "load_migrations",
        lambda *args, **kwargs: {
            "--old": __import__("llama_doctor.core.rules", fromlist=["MigrationRule"]).MigrationRule(
                "r", "--old", "--load-mode none", True, "migrated"
            )
        },
    )
    monkeypatch.setattr(cli, "load_conflicts", lambda *args, **kwargs: [])
    result = runner.invoke(
        cli.app,
        ["fix", "--exe", str(exe), "llama-server --old"],
    )
    assert result.exit_code == 0
    assert "--load-mode none" in result.stdout


def test_check_internal_error_uses_exit_code_2(monkeypatch, tmp_path):
    exe = tmp_path / "llama-server"
    exe.write_text("fake")
    monkeypatch.setattr(cli, "probe_executable", lambda *args, **kwargs: schema())
    monkeypatch.setattr(cli, "load_migrations", lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("boom")))
    result = runner.invoke(
        cli.app,
        ["check", "--json", "--exe", str(exe), "llama-server -c 4096"],
    )
    assert result.exit_code == 2
    assert '"internal_error": "boom"' in result.stdout


def test_version_reports_the_verified_llama_cpp_build():
    result = runner.invoke(cli.app, ["version"])
    assert result.exit_code == 0
    assert str(VERIFIED_LLAMA_CPP_BUILD) in result.stdout
    # The version string itself ends with that build number, which is how
    # llama.cpp tags its own releases.
    assert __version__.endswith(str(VERIFIED_LLAMA_CPP_BUILD))


def test_build_number_is_read_from_the_llama_cpp_version_line():
    text = "version: 0.3.0-dev (build 10731, commit 0eadefebd3)\nbuilt with MSVC"
    assert cli._build_number(text) == 10731
    assert cli._build_number("no build here") is None


def test_probe_notes_when_the_build_differs_from_the_verified_one(monkeypatch, tmp_path):
    exe = tmp_path / "llama-server"
    exe.write_text("fake")
    newer = schema()
    newer.version = f"version: 0.3.0-dev (build {VERIFIED_LLAMA_CPP_BUILD + 500}, commit abc)"
    monkeypatch.setattr(cli, "probe_executable", lambda *args, **kwargs: newer)
    result = runner.invoke(cli.app, ["probe", "--exe", str(exe)])
    assert result.exit_code == 0
    assert "newer" in result.stdout
    assert str(VERIFIED_LLAMA_CPP_BUILD) in result.stdout


def test_probe_is_quiet_when_the_build_matches(monkeypatch, tmp_path):
    exe = tmp_path / "llama-server"
    exe.write_text("fake")
    same = schema()
    same.version = f"version: 0.3.0-dev (build {VERIFIED_LLAMA_CPP_BUILD}, commit abc)"
    monkeypatch.setattr(cli, "probe_executable", lambda *args, **kwargs: same)
    result = runner.invoke(cli.app, ["probe", "--exe", str(exe)])
    assert result.exit_code == 0
    assert "verified against" not in result.stdout.lower()
