from __future__ import annotations

import locale
import os
import re
from dataclasses import replace
from typing import Any

from .core import diagnostics as codes
from .core.models import Diagnostic, ValidationResult

SUPPORTED_LANGUAGES = ("en", "zh", "ja")


def normalize_language(value: str | None, *, default: str = "en") -> str:
    if not value:
        return default
    raw = value.strip().lower().replace("_", "-")
    if raw == "auto":
        return detect_system_language(default=default)
    if raw.startswith("zh"):
        return "zh"
    if raw.startswith("ja") or raw.startswith("jp"):
        return "ja"
    if raw.startswith("en"):
        return "en"
    return default


def detect_system_language(*, default: str = "en") -> str:
    env = os.environ.get("LLAMA_DOCTOR_LANG")
    if env:
        return normalize_language(env, default=default)
    candidates = [
        os.environ.get("LANGUAGE"),
        os.environ.get("LC_ALL"),
        os.environ.get("LC_MESSAGES"),
        os.environ.get("LANG"),
    ]
    try:
        loc, _ = locale.getlocale()
        candidates.append(loc)
    except Exception:
        pass
    for candidate in candidates:
        if not candidate:
            continue
        normalized = normalize_language(candidate, default="")
        if normalized in SUPPORTED_LANGUAGES:
            return normalized
    return default


_TRANSLATIONS: dict[str, dict[str, str]] = {
    # Common
    "language": {"en": "Language", "zh": "语言", "ja": "言語"},
    "english": {"en": "English", "zh": "English", "ja": "English"},
    "chinese": {"en": "中文", "zh": "中文", "ja": "中文"},
    "japanese": {"en": "日本語", "zh": "日本語", "ja": "日本語"},
    "ready": {"en": "Ready", "zh": "就绪", "ja": "準備完了"},
    "error": {"en": "Error", "zh": "错误", "ja": "エラー"},
    "warning": {"en": "Warning", "zh": "警告", "ja": "警告"},
    "info": {"en": "Info", "zh": "信息", "ja": "情報"},
    "ok": {"en": "OK", "zh": "正常", "ja": "正常"},
    "source": {"en": "Source", "zh": "来源", "ja": "出典"},
    "suggested": {"en": "Suggested", "zh": "建议", "ja": "推奨"},
    "errors_warnings": {
        "en": "{errors} errors | {warnings} warnings",
        "zh": "{errors} 个错误 | {warnings} 个警告",
        "ja": "エラー {errors} 件 | 警告 {warnings} 件",
    },
    # GUI
    "gui_executable": {"en": "llama.cpp executable", "zh": "llama.cpp 可执行文件", "ja": "llama.cpp 実行ファイル"},
    "gui_browse": {"en": "Browse…", "zh": "浏览…", "ja": "参照…"},
    # 解析 is "parse" in Japanese and is used for Analyze below; reusing it here
    # left the Probe and Analyze buttons with the same label.
    "gui_probe": {"en": "Probe", "zh": "探测", "ja": "プローブ"},
    "gui_build_not_loaded": {"en": "Build: not loaded", "zh": "Build：未加载", "ja": "Build：未読込"},
    "gui_build_loaded": {
        "en": "Build: {version}    Type: {type}    Flags: {flags}",
        "zh": "Build：{version}    类型：{type}    参数：{flags}",
        "ja": "Build：{version}    種類：{type}    フラグ：{flags}",
    },
    "gui_command_placeholder": {
        "en": "Paste llama-server / llama-cli command here…",
        "zh": "在此粘贴 llama-server / llama-cli 命令…",
        "ja": "ここに llama-server / llama-cli コマンドを貼り付け…",
    },
    "gui_analyze": {"en": "Analyze", "zh": "分析", "ja": "解析"},
    "gui_fix": {"en": "Fix Command", "zh": "修复命令", "ja": "コマンド修正"},
    "gui_normalize": {"en": "Normalize", "zh": "规范化", "ja": "正規化"},
    "gui_copy": {"en": "Copy Result", "zh": "复制结果", "ja": "結果をコピー"},
    "gui_select_title": {"en": "Select llama.cpp executable", "zh": "选择 llama.cpp 可执行文件", "ja": "llama.cpp 実行ファイルを選択"},
    "gui_select_first": {
        "en": "Select a llama.cpp executable first.",
        "zh": "请先选择 llama.cpp 可执行文件。",
        "ja": "先に llama.cpp 実行ファイルを選択してください。",
    },
    "gui_probe_failed": {"en": "Probe failed", "zh": "探测失败", "ja": "プローブに失敗"},
    "gui_schema_loaded": {"en": "Executable schema loaded", "zh": "已加载可执行文件参数表", "ja": "実行ファイルのスキーマを読み込みました"},
    "gui_parse_error": {"en": "Command parse error", "zh": "命令解析错误", "ja": "コマンド解析エラー"},
    "gui_command_health": {"en": "Command Health", "zh": "命令状态", "ja": "コマンド状態"},
    "gui_analysis_complete": {
        "en": "Analysis complete: {errors} errors, {warnings} warnings",
        "zh": "分析完成：{errors} 个错误，{warnings} 个警告",
        "ja": "解析完了：エラー {errors} 件、警告 {warnings} 件",
    },
    "gui_applied_fixes": {"en": "Applied safe fixes:", "zh": "已应用的安全修复：", "ja": "適用した安全な修正："},
    "gui_review_required": {"en": "Review required:", "zh": "需要人工确认：", "ja": "確認が必要："},
    "gui_remaining_errors": {"en": "Remaining errors:", "zh": "剩余错误：", "ja": "残っているエラー："},
    "gui_fix_parse_failed": {
        "en": "Fix incomplete: generated command could not be parsed",
        "zh": "修复未完成：生成的命令无法解析",
        "ja": "修正未完了：生成したコマンドを解析できません",
    },
    "gui_fix_incomplete": {
        "en": "Fix incomplete: {errors} errors, {review} items require review",
        "zh": "修复未完成：{errors} 个错误，{review} 项需要人工确认",
        "ja": "修正未完了：エラー {errors} 件、確認が必要な項目 {review} 件",
    },
    "gui_fix_complete": {"en": "Fix pass complete", "zh": "修复检查完成", "ja": "修正チェック完了"},
    "gui_normalized": {"en": "Command normalized", "zh": "命令已规范化", "ja": "コマンドを正規化しました"},
    "gui_copied": {"en": "Result copied", "zh": "结果已复制", "ja": "結果をコピーしました"},
    # CLI/table
    "cli_title": {"en": "llama-doctor diagnostics", "zh": "llama-doctor 诊断结果", "ja": "llama-doctor 診断結果"},
    "cli_level": {"en": "Level", "zh": "级别", "ja": "レベル"},
    "cli_code": {"en": "Code", "zh": "代码", "ja": "コード"},
    "cli_flag": {"en": "Flag", "zh": "参数", "ja": "フラグ"},
    "cli_message": {"en": "Message", "zh": "说明", "ja": "メッセージ"},
    "cli_suggestion": {"en": "Suggestion", "zh": "建议", "ja": "提案"},
    "cli_errors_warnings": {
        "en": "Errors: {errors}  Warnings: {warnings}",
        "zh": "错误：{errors}  警告：{warnings}",
        "ja": "エラー：{errors}  警告：{warnings}",
    },
    # Probing the executable and parsing the command fail for different reasons;
    # both reported "解析に失敗", so the Japanese message could not say which.
    "cli_probe_failed": {"en": "Probe failed", "zh": "探测失败", "ja": "プローブに失敗"},
    "cli_parse_failed": {"en": "Parse failed", "zh": "解析失败", "ja": "解析に失敗"},
    "cli_internal_error": {"en": "Internal error", "zh": "内部错误", "ja": "内部エラー"},
    "cli_internal_fix_validation": {
        "en": "Internal error while validating fixed command",
        "zh": "验证修复后命令时发生内部错误",
        "ja": "修正後のコマンド検証中に内部エラーが発生しました",
    },
    "cli_applied_fixes": {"en": "Applied safe fixes:", "zh": "已应用的安全修复：", "ja": "適用した安全な修正："},
    "cli_review_required": {"en": "Review required:", "zh": "需要人工确认：", "ja": "確認が必要："},
    "cli_remaining_errors": {
        "en": "Remaining validation errors after safe fixes:",
        "zh": "安全修复后仍有验证错误：",
        "ja": "安全な修正後も検証エラーが残っています：",
    },
    "cli_type": {"en": "Type", "zh": "类型", "ja": "種類"},
    "cli_version": {"en": "Version", "zh": "版本", "ja": "バージョン"},
    "cli_parsed_flags": {"en": "Parsed flags", "zh": "已解析参数", "ja": "解析済みフラグ"},
    "cli_build_difference": {
        "en": "This build is {direction} than the one llama-doctor {version} was verified against (build {verified}). Checks still run against this build's own --help.",
        "zh": "这个 build 比 llama-doctor {version} 验证基线（build {verified}）{direction}。检查仍以当前 build 自己的 --help 为准。",
        "ja": "この build は llama-doctor {version} の検証基準（build {verified}）より{direction}です。検証は現在選択した build 自身の --help を基準に実行されます。",
    },
    "direction_newer": {"en": "newer", "zh": "更新", "ja": "新しい"},
    "direction_older": {"en": "older", "zh": "更旧", "ja": "古い"},
    "cli_verified": {
        "en": "Verified against llama.cpp {version} (build {build}).",
        "zh": "验证基线：llama.cpp {version}（build {build}）。",
        "ja": "検証基準：llama.cpp {version}（build {build}）。",
    },
    "cli_other_builds": {
        "en": "Other builds work too: the flag schema is read from the executable you select.",
        "zh": "其他 build 也可使用：参数表会直接从你选择的可执行文件中读取。",
        "ja": "他の build でも利用できます。フラグスキーマは選択した実行ファイルから直接読み取ります。",
    },
}


def tr(key: str, lang: str = "en", **kwargs: Any) -> str:
    lang = normalize_language(lang)
    values = _TRANSLATIONS.get(key)
    if values is None:
        return key.format(**kwargs) if kwargs else key
    text = values.get(lang) or values.get("en") or key
    try:
        return text.format(**kwargs)
    except (KeyError, ValueError):
        return text


def severity_label(severity: str, lang: str) -> str:
    return tr(severity if severity in {"error", "warning", "info", "ok"} else "info", lang)


def _quoted(value: str | None) -> str:
    return repr(value) if value is not None else ""


def diagnostic_message(diagnostic: Diagnostic, lang: str) -> str:
    lang = normalize_language(lang)
    if lang == "en":
        return diagnostic.message

    flag = diagnostic.flag or ""
    value = _quoted(diagnostic.value)
    code = diagnostic.code

    zh: dict[str, str] = {
        codes.EMPTY_COMMAND: "命令为空。",
        codes.EXECUTABLE_MISMATCH: "命令中的可执行文件名与当前选择的可执行文件不一致；验证以当前选择的文件为准。",
        codes.UNKNOWN_FLAG: f"当前 build 不支持参数 {flag}。",
        codes.MIGRATION_REQUIRED: f"参数 {flag} 已从当前 build 移除，需要迁移后才能运行。",
        codes.MIGRATION_TARGET_UNAVAILABLE: f"参数 {flag} 需要迁移，但建议的目标参数在当前 build 中不可用。",
        codes.REMOVED_FLAG: f"参数 {flag} 已在当前 build 中移除，运行时会被拒绝。",
        codes.DEPRECATED_FLAG: f"参数 {flag} 已被当前 build 标记为弃用。",
        codes.MISSING_VALUE: f"参数 {flag} 缺少值。",
        codes.UNEXPECTED_VALUE: f"当前 build 中参数 {flag} 不接受值{(' ' + value) if value else ''}。",
        codes.INVALID_VALUE: f"参数 {flag} 的值 {value} 无效。",
        codes.INVALID_RANGE: f"参数 {flag} 的值 {value} 超出当前 build 支持的范围。",
        codes.ENV_OVERRIDE: f"参数 {flag} 的命令行值会覆盖对应的环境变量。",
        codes.DUPLICATE_FLAG: f"参数 {flag} 被重复指定。",
        codes.ALIAS_DUPLICATE: f"参数 {flag} 通过不同别名被重复指定。",
        codes.CONFLICTING_FLAGS: f"检测到冲突参数：{flag}。最终行为可能取决于参数顺序。",
        codes.PARSE_ERROR: (
            "命令中存在未闭合的引号。"
            if diagnostic.message.startswith("Unterminated ")
            else f"命令解析失败：{diagnostic.message}"
        ),
        "OK": "未发现问题。",
    }
    ja: dict[str, str] = {
        codes.EMPTY_COMMAND: "コマンドが空です。",
        codes.EXECUTABLE_MISMATCH: "コマンド内の実行ファイル名と選択した実行ファイルが一致しません。検証は選択した実行ファイルを基準に行います。",
        codes.UNKNOWN_FLAG: f"現在の build はフラグ {flag} をサポートしていません。",
        codes.MIGRATION_REQUIRED: f"フラグ {flag} は現在の build から削除されており、実行前に移行が必要です。",
        codes.MIGRATION_TARGET_UNAVAILABLE: f"フラグ {flag} は移行が必要ですが、推奨される移行先が現在の build では利用できません。",
        codes.REMOVED_FLAG: f"フラグ {flag} は現在の build で削除されており、実行時に拒否されます。",
        codes.DEPRECATED_FLAG: f"フラグ {flag} は現在の build で非推奨です。",
        codes.MISSING_VALUE: f"フラグ {flag} の値がありません。",
        codes.UNEXPECTED_VALUE: f"現在の build ではフラグ {flag} は値{(' ' + value) if value else ''}を受け取りません。",
        codes.INVALID_VALUE: f"フラグ {flag} の値 {value} は無効です。",
        codes.INVALID_RANGE: f"フラグ {flag} の値 {value} は現在の build がサポートする範囲外です。",
        codes.ENV_OVERRIDE: f"フラグ {flag} の CLI 値が対応する環境変数を上書きします。",
        codes.DUPLICATE_FLAG: f"フラグ {flag} が重複しています。",
        codes.ALIAS_DUPLICATE: f"フラグ {flag} が異なるエイリアス経由で重複しています。",
        codes.CONFLICTING_FLAGS: f"競合するフラグを検出しました：{flag}。最終的な挙動は引数の順序に依存する可能性があります。",
        codes.PARSE_ERROR: (
            "コマンド内に閉じられていない引用符があります。"
            if diagnostic.message.startswith("Unterminated ")
            else f"コマンド解析に失敗しました：{diagnostic.message}"
        ),
        "OK": "問題は見つかりませんでした。",
    }
    table = zh if lang == "zh" else ja
    return table.get(code, diagnostic.message)


def diagnostic_suggestion(diagnostic: Diagnostic, lang: str) -> str | None:
    language = normalize_language(lang)
    suggestion = diagnostic.suggestion
    if suggestion is None or language == "en":
        return suggestion

    if diagnostic.code == codes.EXECUTABLE_MISMATCH:
        return (
            "验证以当前选择的可执行文件为准。"
            if language == "zh"
            else "検証は現在選択している実行ファイルを基準に行います。"
        )

    # Most other suggestions are executable flag names or replacement command
    # fragments. Those must never be translated.
    return suggestion


def localized_diagnostic(diagnostic: Diagnostic, lang: str) -> Diagnostic:
    return replace(
        diagnostic,
        message=diagnostic_message(diagnostic, lang),
        suggestion=diagnostic_suggestion(diagnostic, lang),
    )


def validation_to_dict(result: ValidationResult, lang: str) -> dict[str, Any]:
    language = normalize_language(lang)
    payload = result.to_dict()
    payload["language"] = language
    payload["diagnostics"] = [localized_diagnostic(d, language).to_dict() for d in result.diagnostics]
    return payload


_BLOCKED_FIX_RE = re.compile(
    r"^(?P<prefix>.+?) \(not auto-applied because multiple arguments affect (?P<target>.+?)\)$"
)


def localize_fix_item(item: str, lang: str) -> str:
    language = normalize_language(lang)
    if language == "en":
        return item
    match = _BLOCKED_FIX_RE.match(item)
    if not match:
        return item
    prefix = match.group("prefix")
    target = match.group("target")
    if language == "zh":
        return f"{prefix}（未自动应用：多个参数都会影响 {target}）"
    return f"{prefix}（自動適用しません：複数の引数が {target} に影響します）"


def localize_probe_error(message: str, lang: str) -> str:
    language = normalize_language(lang)
    if language == "en":
        return message
    if message.startswith("Executable not found:"):
        detail = message.split(":", 1)[1].strip()
        return (f"找不到可执行文件：{detail}" if language == "zh" else f"実行ファイルが見つかりません：{detail}")
    if message == "Executable returned empty --help output":
        return "可执行文件返回了空的 --help 输出" if language == "zh" else "実行ファイルの --help 出力が空です"
    if message == "Could not parse any command-line options from --help output":
        return "无法从 --help 输出中解析任何命令行参数" if language == "zh" else "--help 出力からコマンドラインオプションを解析できませんでした"
    return message
