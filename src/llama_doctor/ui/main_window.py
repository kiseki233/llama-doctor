from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..core import diagnostics as codes
from ..core.command_parser import CommandParseError, parse_command
from ..core.executable_probe import ProbeError, probe_executable
from ..core.fixer import fix_command
from ..core.models import Diagnostic
from ..core.normalizer import normalize_command
from ..core.rules import load_conflicts, load_migrations
from ..core.validator import validate_command
from ..i18n import (
    detect_system_language,
    diagnostic_message,
    diagnostic_suggestion,
    localize_fix_item,
    localize_probe_error,
    normalize_language,
    severity_label,
    tr,
)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("llama-doctor")
        self.resize(1000, 720)
        self.schema = None
        self.schema_path: str | None = None
        self.settings = QSettings("llama-doctor", "llama-doctor")
        saved = self.settings.value("language", "auto")
        self.lang = detect_system_language() if saved == "auto" else normalize_language(str(saved))
        self._build_ui()
        self._retranslate_ui()

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)

        language_row = QHBoxLayout()
        language_row.addStretch(1)
        self.language_label = QLabel()
        self.language_combo = QComboBox()
        self.language_combo.addItem("中文", "zh")
        self.language_combo.addItem("日本語", "ja")
        self.language_combo.addItem("English", "en")
        index = self.language_combo.findData(self.lang)
        if index >= 0:
            self.language_combo.setCurrentIndex(index)
        self.language_combo.currentIndexChanged.connect(self._on_language_changed)
        language_row.addWidget(self.language_label)
        language_row.addWidget(self.language_combo)
        layout.addLayout(language_row)

        exe_row = QHBoxLayout()
        self.exe_label = QLabel()
        self.exe_edit = QLineEdit()
        self.exe_edit.textChanged.connect(self._on_executable_text_changed)
        self.browse_button = QPushButton()
        self.browse_button.clicked.connect(self._browse)
        self.probe_button = QPushButton()
        self.probe_button.clicked.connect(self._probe)
        exe_row.addWidget(self.exe_label)
        exe_row.addWidget(self.exe_edit, 1)
        exe_row.addWidget(self.browse_button)
        exe_row.addWidget(self.probe_button)
        layout.addLayout(exe_row)

        self.build_label = QLabel()
        layout.addWidget(self.build_label)

        self.command_edit = QPlainTextEdit()
        self.result_edit = QPlainTextEdit()
        self.result_edit.setReadOnly(True)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.command_edit)
        splitter.addWidget(self.result_edit)
        splitter.setSizes([320, 320])
        layout.addWidget(splitter, 1)

        buttons = QHBoxLayout()
        self.analyze_button = QPushButton()
        self.analyze_button.clicked.connect(self._analyze)
        self.fix_button = QPushButton()
        self.fix_button.clicked.connect(self._fix)
        self.normalize_button = QPushButton()
        self.normalize_button.clicked.connect(self._normalize)
        self.copy_button = QPushButton()
        self.copy_button.clicked.connect(self._copy)
        buttons.addWidget(self.analyze_button)
        buttons.addWidget(self.fix_button)
        buttons.addWidget(self.normalize_button)
        buttons.addStretch(1)
        buttons.addWidget(self.copy_button)
        layout.addLayout(buttons)

        self.setCentralWidget(root)

    def _on_language_changed(self) -> None:
        data = self.language_combo.currentData()
        self.lang = normalize_language(str(data))
        self.settings.setValue("language", self.lang)
        self._retranslate_ui()

    def _update_build_label(self) -> None:
        if self.schema is None:
            self.build_label.setText(tr("gui_build_not_loaded", self.lang))
            return
        self.build_label.setText(
            tr(
                "gui_build_loaded",
                self.lang,
                version=self.schema.version,
                type=self.schema.executable_type,
                flags=len(self.schema.flags),
            )
        )

    def _retranslate_ui(self) -> None:
        self.language_label.setText(tr("language", self.lang))
        self.exe_label.setText(tr("gui_executable", self.lang))
        self.browse_button.setText(tr("gui_browse", self.lang))
        self.probe_button.setText(tr("gui_probe", self.lang))
        self.command_edit.setPlaceholderText(tr("gui_command_placeholder", self.lang))
        self.analyze_button.setText(tr("gui_analyze", self.lang))
        self.fix_button.setText(tr("gui_fix", self.lang))
        self.normalize_button.setText(tr("gui_normalize", self.lang))
        self.copy_button.setText(tr("gui_copy", self.lang))
        self._update_build_label()
        self.statusBar().showMessage(tr("ready", self.lang))

    def _on_executable_text_changed(self) -> None:
        current = self.exe_edit.text().strip()
        if self.schema_path is not None and current != self.schema_path:
            self.schema = None
            self.schema_path = None
            self._update_build_label()

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, tr("gui_select_title", self.lang))
        if path:
            self.exe_edit.setText(path)
            self._probe()

    def _probe(self) -> bool:
        path = self.exe_edit.text().strip()
        if not path:
            QMessageBox.warning(self, "llama-doctor", tr("gui_select_first", self.lang))
            return False
        try:
            self.schema = probe_executable(path)
        except ProbeError as exc:
            QMessageBox.critical(
                self,
                tr("gui_probe_failed", self.lang),
                localize_probe_error(str(exc), self.lang),
            )
            self.schema = None
            self.schema_path = None
            self._update_build_label()
            return False
        self.schema_path = path
        self._update_build_label()
        self.statusBar().showMessage(tr("gui_schema_loaded", self.lang))
        return True

    def _rules(self):
        rules = Path(__file__).resolve().parents[1] / "rules"
        return load_migrations(rules / "migrations.json"), load_conflicts(rules / "conflicts.json")

    def _ensure_schema(self) -> bool:
        path = self.exe_edit.text().strip()
        return (self.schema is not None and self.schema_path == path) or self._probe()

    def _parse(self):
        try:
            return parse_command(self.command_edit.toPlainText(), self.schema)
        except CommandParseError as exc:
            diagnostic = Diagnostic(severity="error", code=codes.PARSE_ERROR, message=str(exc))
            self.result_edit.setPlainText(
                f"[{severity_label('error', self.lang)}] {codes.PARSE_ERROR}\n"
                f"  {diagnostic_message(diagnostic, self.lang)}"
            )
            self.statusBar().showMessage(tr("gui_parse_error", self.lang))
            return None

    def _analyze(self) -> None:
        if not self._ensure_schema():
            return
        parsed = self._parse()
        if parsed is None:
            return
        migrations, conflicts = self._rules()
        result = validate_command(parsed, self.schema, migrations, conflicts, self.exe_edit.text().strip(), os.environ)
        lines = [
            f"{tr('gui_command_health', self.lang)}: "
            f"{tr('errors_warnings', self.lang, errors=result.errors, warnings=result.warnings)}",
            "",
        ]
        for diagnostic in result.diagnostics:
            flag = f" {diagnostic.flag}" if diagnostic.flag else ""
            lines.append(f"[{severity_label(diagnostic.severity, self.lang)}] {diagnostic.code}{flag}")
            lines.append(f"  {diagnostic_message(diagnostic, self.lang)}")
            suggestion = diagnostic_suggestion(diagnostic, self.lang)
            if suggestion:
                lines.append(f"  {tr('suggested', self.lang)}: {suggestion}")
            if diagnostic.source:
                lines.append(f"  {tr('source', self.lang)}: {diagnostic.source}")
            lines.append("")
        self.result_edit.setPlainText("\n".join(lines))
        self.statusBar().showMessage(
            tr("gui_analysis_complete", self.lang, errors=result.errors, warnings=result.warnings)
        )

    def _fix(self) -> None:
        if not self._ensure_schema():
            return
        parsed = self._parse()
        if parsed is None:
            return
        migrations, conflicts = self._rules()
        fixed = fix_command(parsed, self.schema, migrations)
        lines = [fixed.command]
        if fixed.applied:
            lines += [
                "",
                tr("gui_applied_fixes", self.lang),
                *[f"- {localize_fix_item(item, self.lang)}" for item in fixed.applied],
            ]
        if fixed.review_required:
            lines += [
                "",
                tr("gui_review_required", self.lang),
                *[f"- {localize_fix_item(item, self.lang)}" for item in fixed.review_required],
            ]

        try:
            reparsed = parse_command(fixed.command, self.schema)
            post_result = validate_command(
                reparsed,
                self.schema,
                migrations,
                conflicts,
                self.exe_edit.text().strip(),
                os.environ,
            )
        except CommandParseError as exc:
            diagnostic = Diagnostic(severity="error", code=codes.PARSE_ERROR, message=str(exc))
            lines += [
                "",
                tr("gui_remaining_errors", self.lang),
                f"- {codes.PARSE_ERROR}: {diagnostic_message(diagnostic, self.lang)}",
            ]
            self.result_edit.setPlainText("\n".join(lines))
            self.statusBar().showMessage(tr("gui_fix_parse_failed", self.lang))
            return

        remaining = [item for item in post_result.diagnostics if item.severity == "error"]
        if remaining:
            lines += ["", tr("gui_remaining_errors", self.lang)]
            for item in remaining:
                flag = f" {item.flag}" if item.flag else ""
                lines.append(f"- {item.code}{flag}: {diagnostic_message(item, self.lang)}")

        self.result_edit.setPlainText("\n".join(lines))
        if fixed.review_required or remaining:
            self.statusBar().showMessage(
                tr(
                    "gui_fix_incomplete",
                    self.lang,
                    errors=len(remaining),
                    review=len(fixed.review_required),
                )
            )
        else:
            self.statusBar().showMessage(tr("gui_fix_complete", self.lang))

    def _normalize(self) -> None:
        if not self._ensure_schema():
            return
        parsed = self._parse()
        if parsed is None:
            return
        self.result_edit.setPlainText(normalize_command(parsed, self.schema))
        self.statusBar().showMessage(tr("gui_normalized", self.lang))

    def _copy(self) -> None:
        QApplication.clipboard().setText(self.result_edit.toPlainText())
        self.statusBar().showMessage(tr("gui_copied", self.lang))


def run() -> int:
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    window.show()
    return app.exec()
