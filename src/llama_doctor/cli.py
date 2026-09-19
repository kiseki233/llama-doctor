from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from . import VERIFIED_LLAMA_CPP_BUILD, VERIFIED_LLAMA_CPP_VERSION, __version__
from .core import diagnostics as codes
from .core.command_parser import CommandParseError, parse_command
from .core.executable_probe import ProbeError, probe_executable
from .core.fixer import fix_command
from .core.models import Diagnostic, ValidationResult
from .core.normalizer import normalize_command
from .core.rules import load_conflicts, load_migrations
from .core.validator import validate_command
from .i18n import (
    diagnostic_message,
    diagnostic_suggestion,
    localize_fix_item,
    localize_probe_error,
    normalize_language,
    severity_label,
    tr,
    validation_to_dict,
)

app = typer.Typer(
    help=(
        "Lint, diagnose and migrate llama.cpp commands. / "
        "检查、诊断并迁移 llama.cpp 命令。 / "
        "llama.cpp コマンドを検査・診断・移行します。"
    ),
    no_args_is_help=True,
)
console = Console()

LANG_HELP = "Output language: en, zh, or ja. / 输出语言 / 出力言語"


def _rules_dir() -> Path:
    return Path(__file__).resolve().parent / "rules"


_BUILD_NUMBER = re.compile(r"\bbuild\s+(\d+)", re.IGNORECASE)


def _build_number(version_text: str) -> int | None:
    """Pull llama.cpp's build number out of its --version line."""
    match = _BUILD_NUMBER.search(version_text or "")
    return int(match.group(1)) if match else None


def _read_command(command: str) -> str:
    if command == "-":
        return sys.stdin.read()
    try:
        path = Path(command)
        if path.exists() and path.is_file():
            return path.read_text(encoding="utf-8-sig")
    except OSError:
        pass
    return command


def _parse_error_result(exc: CommandParseError) -> ValidationResult:
    return ValidationResult(
        [Diagnostic(severity="error", code=codes.PARSE_ERROR, message=str(exc))]
    )


def _analyze(executable: Path, command_text: str, *, use_cache: bool = True):
    schema = probe_executable(executable, use_cache=use_cache)
    migrations = load_migrations(_rules_dir() / "migrations.json")
    conflicts = load_conflicts(_rules_dir() / "conflicts.json")
    parsed = parse_command(command_text, schema)
    result = validate_command(parsed, schema, migrations, conflicts, str(executable), os.environ)
    return schema, parsed, result, migrations, conflicts


def _print_result(result: ValidationResult, lang: str = "en") -> None:
    language = normalize_language(lang)
    table = Table(title=tr("cli_title", language))
    table.add_column(tr("cli_level", language))
    table.add_column(tr("cli_code", language))
    table.add_column(tr("cli_flag", language))
    table.add_column(tr("cli_message", language))
    table.add_column(tr("cli_suggestion", language))
    for diagnostic in result.diagnostics:
        table.add_row(
            severity_label(diagnostic.severity, language),
            diagnostic.code,
            diagnostic.flag or "",
            diagnostic_message(diagnostic, language),
            diagnostic_suggestion(diagnostic, language) or "",
        )
    console.print(table)
    console.print(
        tr("cli_errors_warnings", language, errors=result.errors, warnings=result.warnings)
    )


@app.command(help="Validate a command. / 验证命令。 / コマンドを検証します。")
def check(
    command: str = typer.Argument(..., help="Command text / 命令文本 / コマンド文字列；'-' = stdin；也可传入文本文件路径。"),
    executable: Path = typer.Option(..., "--exe", "-e", exists=True, dir_okay=False, help="Path to llama-server/llama-cli. / 可执行文件路径 / 実行ファイルのパス"),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON. / 输出 JSON / JSON を出力"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Ignore cache and probe --help again. / 忽略缓存重新探测 / キャッシュを無視して再解析"),
    lang: str = typer.Option("en", "--lang", help=LANG_HELP),
):
    """Validate a llama.cpp command against the selected executable build."""
    language = normalize_language(lang)
    try:
        _, _, result, _, _ = _analyze(executable, _read_command(command), use_cache=not no_cache)
    except CommandParseError as exc:
        result = _parse_error_result(exc)
    except ProbeError as exc:
        message = localize_probe_error(str(exc), language)
        if json_output:
            typer.echo(json.dumps({"valid": False, "language": language, "probe_error": message}, ensure_ascii=False))
        else:
            console.print(f"[red]{tr('cli_probe_failed', language)}:[/red] {message}")
        raise typer.Exit(3)
    except Exception as exc:
        if json_output:
            typer.echo(json.dumps({"valid": False, "language": language, "internal_error": str(exc)}, ensure_ascii=False))
        else:
            console.print(f"[red]{tr('cli_internal_error', language)}:[/red] {exc}")
        raise typer.Exit(2)

    if json_output:
        typer.echo(json.dumps(validation_to_dict(result, language), ensure_ascii=False, indent=2))
    else:
        _print_result(result, language)

    raise typer.Exit(0 if result.valid else 1)


@app.command(help="Apply safe fixes. / 应用安全修复。 / 安全な修正を適用します。")
def fix(
    command: str = typer.Argument(..., help="Command text / 命令文本 / コマンド文字列；'-' = stdin；也可传入文本文件路径。"),
    executable: Path = typer.Option(..., "--exe", "-e", exists=True, dir_okay=False),
    no_cache: bool = typer.Option(False, "--no-cache"),
    lang: str = typer.Option("en", "--lang", help=LANG_HELP),
):
    """Apply safe migration rules and normalize aliases."""
    language = normalize_language(lang)
    try:
        schema, parsed, _, migrations, conflicts = _analyze(
            executable, _read_command(command), use_cache=not no_cache
        )
    except CommandParseError as exc:
        diagnostic = Diagnostic(severity="error", code=codes.PARSE_ERROR, message=str(exc))
        console.print(f"[red]{tr('cli_parse_failed', language)}:[/red] {diagnostic_message(diagnostic, language)}")
        raise typer.Exit(1)
    except ProbeError as exc:
        console.print(
            f"[red]{tr('cli_probe_failed', language)}:[/red] {localize_probe_error(str(exc), language)}"
        )
        raise typer.Exit(3)
    except Exception as exc:
        console.print(f"[red]{tr('cli_internal_error', language)}:[/red] {exc}")
        raise typer.Exit(2)

    try:
        fixed = fix_command(parsed, schema, migrations, normalize_aliases=True)
    except Exception as exc:
        console.print(f"[red]{tr('cli_internal_error', language)}:[/red] {exc}")
        raise typer.Exit(2)

    typer.echo(fixed.command)
    if fixed.applied:
        console.print(f"[green]{tr('cli_applied_fixes', language)}[/green]")
        for item in fixed.applied:
            console.print(f"  - {localize_fix_item(item, language)}")
    if fixed.review_required:
        console.print(f"[yellow]{tr('cli_review_required', language)}[/yellow]")
        for item in fixed.review_required:
            console.print(f"  - {localize_fix_item(item, language)}")

    try:
        reparsed = parse_command(fixed.command, schema)
        post_result = validate_command(
            reparsed, schema, migrations, conflicts, str(executable), os.environ
        )
    except Exception as exc:
        console.print(f"[red]{tr('cli_internal_fix_validation', language)}:[/red] {exc}")
        raise typer.Exit(2)

    if not post_result.valid:
        console.print(f"[red]{tr('cli_remaining_errors', language)}[/red]")
        _print_result(post_result, language)

    if fixed.review_required or not post_result.valid:
        raise typer.Exit(1)


@app.command(help="Normalize aliases. / 规范化参数别名。 / エイリアスを正規化します。")
def normalize(
    command: str = typer.Argument(..., help="Command text / 命令文本 / コマンド文字列；'-' = stdin；也可传入文本文件路径。"),
    executable: Path = typer.Option(..., "--exe", "-e", exists=True, dir_okay=False),
    no_cache: bool = typer.Option(False, "--no-cache"),
    lang: str = typer.Option("en", "--lang", help=LANG_HELP),
):
    """Normalize aliases to canonical long flags."""
    language = normalize_language(lang)
    try:
        schema = probe_executable(executable, use_cache=not no_cache)
        parsed = parse_command(_read_command(command), schema)
    except CommandParseError as exc:
        diagnostic = Diagnostic(severity="error", code=codes.PARSE_ERROR, message=str(exc))
        console.print(f"[red]{tr('cli_parse_failed', language)}:[/red] {diagnostic_message(diagnostic, language)}")
        raise typer.Exit(1)
    except ProbeError as exc:
        console.print(
            f"[red]{tr('cli_probe_failed', language)}:[/red] {localize_probe_error(str(exc), language)}"
        )
        raise typer.Exit(3)
    except Exception as exc:
        console.print(f"[red]{tr('cli_internal_error', language)}:[/red] {exc}")
        raise typer.Exit(2)
    typer.echo(normalize_command(parsed, schema))


@app.command("probe", help="Inspect an executable. / 检查可执行文件。 / 実行ファイルを解析します。")
def probe(
    executable: Path = typer.Option(..., "--exe", "-e", exists=True, dir_okay=False),
    json_output: bool = typer.Option(False, "--json"),
    no_cache: bool = typer.Option(False, "--no-cache"),
    lang: str = typer.Option("en", "--lang", help=LANG_HELP),
):
    """Inspect the selected llama.cpp executable and parsed option schema."""
    language = normalize_language(lang)
    try:
        schema = probe_executable(executable, use_cache=not no_cache)
    except ProbeError as exc:
        message = localize_probe_error(str(exc), language)
        if json_output:
            typer.echo(json.dumps({"language": language, "probe_error": message}, ensure_ascii=False))
        else:
            console.print(f"[red]{tr('cli_probe_failed', language)}:[/red] {message}")
        raise typer.Exit(3)
    except Exception as exc:
        if json_output:
            typer.echo(json.dumps({"language": language, "internal_error": str(exc)}, ensure_ascii=False))
        else:
            console.print(f"[red]{tr('cli_internal_error', language)}:[/red] {exc}")
        raise typer.Exit(2)

    probed_build = _build_number(schema.version)
    if json_output:
        payload = {
            "language": language,
            "executable": str(executable),
            "type": schema.executable_type,
            "version": schema.version,
            "build": probed_build,
            "verified_build": VERIFIED_LLAMA_CPP_BUILD,
            "flag_count": len(schema.flags),
            "flags": {
                name: {
                    "aliases": definition.aliases,
                    "requires_value": definition.requires_value,
                    "value_optional": definition.value_optional,
                    "value_name": definition.value_name,
                    "value_type": definition.value_type,
                    "choices": definition.choices,
                    "env_var": definition.env_var,
                }
                for name, definition in schema.flags.items()
            },
        }
        typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        console.print(f"{tr('cli_type', language)}: {schema.executable_type}")
        console.print(f"{tr('cli_version', language)}: {schema.version}")
        console.print(f"{tr('cli_parsed_flags', language)}: {len(schema.flags)}")
        if probed_build is not None and probed_build != VERIFIED_LLAMA_CPP_BUILD:
            direction_key = "direction_newer" if probed_build > VERIFIED_LLAMA_CPP_BUILD else "direction_older"
            console.print(
                "[dim]"
                + tr(
                    "cli_build_difference",
                    language,
                    direction=tr(direction_key, language),
                    version=__version__,
                    verified=VERIFIED_LLAMA_CPP_BUILD,
                )
                + "[/dim]"
            )


@app.command(help="Show version. / 显示版本。 / バージョンを表示します。")
def version(
    json_output: bool = typer.Option(False, "--json"),
    lang: str = typer.Option("en", "--lang", help=LANG_HELP),
):
    """Print the version and the llama.cpp build this release was verified against."""
    language = normalize_language(lang)
    if json_output:
        typer.echo(
            json.dumps(
                {
                    "language": language,
                    "version": __version__,
                    "verified_llama_cpp_version": VERIFIED_LLAMA_CPP_VERSION,
                    "verified_llama_cpp_build": VERIFIED_LLAMA_CPP_BUILD,
                },
                ensure_ascii=False,
            )
        )
        return
    typer.echo(__version__)
    typer.echo(
        tr(
            "cli_verified",
            language,
            version=VERIFIED_LLAMA_CPP_VERSION,
            build=VERIFIED_LLAMA_CPP_BUILD,
        )
    )
    typer.echo(tr("cli_other_builds", language))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
