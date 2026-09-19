from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Severity = Literal["error", "warning", "info", "ok"]


@dataclass(slots=True)
class FlagDefinition:
    name: str
    aliases: list[str] = field(default_factory=list)
    requires_value: bool = False
    value_optional: bool = False
    value_name: str | None = None
    value_type: str | None = None
    choices: list[str] | None = None
    min_value: float | None = None
    max_value: float | None = None
    env_var: str | None = None
    deprecated: bool = False
    # A flag the build still lists in --help but refuses at runtime, saying the
    # argument has been removed. Deprecated still runs; removed does not, so the
    # two cannot share a severity.
    removed: bool = False
    removal_hint: str | None = None
    description: str = ""

    @property
    def all_names(self) -> list[str]:
        return [self.name, *self.aliases]

    @property
    def takes_value(self) -> bool:
        return self.requires_value or self.value_optional


@dataclass(slots=True)
class BuildSchema:
    executable_type: str
    version: str
    flags: dict[str, FlagDefinition]
    raw_help: str = ""

    def alias_map(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for canonical, definition in self.flags.items():
            out[canonical] = canonical
            for alias in definition.aliases:
                out[alias] = canonical
        return out


@dataclass(slots=True)
class CommandArgument:
    raw_flag: str
    canonical_flag: str | None
    value: str | None
    position: int


@dataclass(slots=True)
class ParsedCommand:
    executable: str | None
    arguments: list[CommandArgument]
    raw_tokens: list[str]
    source: str
    # Tokens that belong to no flag -- a bare word, or the shell's ``--``
    # separator. Each is stored with the number of arguments that preceded it so
    # that a rewritten command can put it back where the user typed it. Without
    # this, ``fix`` quietly shortens the command it hands back.
    extras: list[tuple[int, str]] = field(default_factory=list)


@dataclass(slots=True)
class Diagnostic:
    severity: Severity
    code: str
    message: str
    flag: str | None = None
    value: str | None = None
    suggestion: str | None = None
    source: str | None = None
    safe_fix: bool = False
    position: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ValidationResult:
    diagnostics: list[Diagnostic]

    @property
    def errors(self) -> int:
        return sum(d.severity == "error" for d in self.diagnostics)

    @property
    def warnings(self) -> int:
        return sum(d.severity == "warning" for d in self.diagnostics)

    @property
    def valid(self) -> bool:
        return self.errors == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "diagnostics": [d.to_dict() for d in self.diagnostics],
        }
