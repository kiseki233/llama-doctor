from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class MigrationRule:
    id: str
    old_flag: str
    replacement: str
    safe: bool
    note: str = ""
    source: str = ""


@dataclass(slots=True)
class ConflictRule:
    id: str
    flags: list[str]
    severity: str = "warning"
    note: str = ""
    source: str = ""


def load_migrations(path: str | Path) -> dict[str, MigrationRule]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rules = [MigrationRule(**item) for item in data.get("rules", [])]
    return {r.old_flag: r for r in rules}


def load_conflicts(path: str | Path) -> list[ConflictRule]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [ConflictRule(**item) for item in data.get("rules", [])]
