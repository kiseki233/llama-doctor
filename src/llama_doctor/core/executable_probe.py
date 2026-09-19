from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import asdict, fields
from pathlib import Path

from .help_parser import parse_help
from .models import BuildSchema, FlagDefinition


# Bumped when the *meaning* of a parse changes -- new inference rules, a wider
# flag-name pattern -- because the cached result would otherwise stay wrong.
# 4: flag names may contain interior dots (--fim-qwen-1.5b-default); wildcard
#    families in help text no longer create phantom flags; removed arguments are
#    recognised from their help wording.
SCHEMA_CACHE_FORMAT = 4


def _schema_fingerprint() -> str:
    """Identify the shape of a cached FlagDefinition.

    Adding a field to FlagDefinition silently changes what a cache entry can
    hold: an older entry loads without the field, so the new check it feeds goes
    quiet instead of failing loudly. Folding the field names into the cache key
    retires those entries automatically, and removes the need to remember a
    manual bump for every schema change.
    """
    names = ",".join(f.name for f in fields(FlagDefinition))
    return hashlib.sha256(names.encode("utf-8")).hexdigest()[:8]


SCHEMA_FIELDS_FINGERPRINT = _schema_fingerprint()


class ProbeError(RuntimeError):
    pass


def _run(path: Path, arg: str, timeout: float = 8.0) -> str:
    try:
        completed = subprocess.run(
            [str(path), arg],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ProbeError(str(exc)) from exc
    return completed.stdout or ""


def detect_executable_type(path: Path) -> str:
    name = path.stem.lower()
    if "server" in name:
        return "llama-server"
    if "cli" in name:
        return "llama-cli"
    return name


def schema_cache_key(path: str | os.PathLike[str]) -> str:
    exe = Path(path)
    stat = exe.stat()
    raw = (
        f"v{SCHEMA_CACHE_FORMAT}|{SCHEMA_FIELDS_FINGERPRINT}"
        f"|{exe.resolve()}|{stat.st_size}|{stat.st_mtime_ns}"
    ).encode("utf-8", "surrogatepass")
    return hashlib.sha256(raw).hexdigest()[:20]


def default_cache_dir() -> Path:
    override = os.environ.get("LLAMA_DOCTOR_CACHE_DIR")
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return root / "llama-doctor" / "cache"
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "llama-doctor"


def save_schema(schema: BuildSchema, destination: str | os.PathLike[str]) -> None:
    data = {
        "cache_format": SCHEMA_CACHE_FORMAT,
        "schema_fields": SCHEMA_FIELDS_FINGERPRINT,
        "executable_type": schema.executable_type,
        "version": schema.version,
        "raw_help": schema.raw_help,
        "flags": {name: asdict(defn) for name, defn in schema.flags.items()},
    }
    dest = Path(destination)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_schema(source: str | os.PathLike[str]) -> BuildSchema:
    data = json.loads(Path(source).read_text(encoding="utf-8"))
    if data.get("cache_format") != SCHEMA_CACHE_FORMAT:
        raise ValueError("Unsupported schema cache format")
    if data.get("schema_fields") != SCHEMA_FIELDS_FINGERPRINT:
        raise ValueError("Schema cache was written by a different FlagDefinition shape")
    flags = {name: FlagDefinition(**value) for name, value in data["flags"].items()}
    return BuildSchema(
        executable_type=data["executable_type"],
        version=data["version"],
        flags=flags,
        raw_help=data.get("raw_help", ""),
    )


def probe_executable(
    path: str | os.PathLike[str],
    *,
    use_cache: bool = True,
    cache_dir: str | os.PathLike[str] | None = None,
) -> BuildSchema:
    exe = Path(path)
    if not exe.exists() or not exe.is_file():
        raise ProbeError(f"Executable not found: {exe}")

    cache_file: Path | None = None
    if use_cache:
        try:
            root = Path(cache_dir) if cache_dir is not None else default_cache_dir()
            cache_file = root / f"{schema_cache_key(exe)}.json"
            if cache_file.exists():
                cached = load_schema(cache_file)
                if not cached.flags:
                    raise ValueError("Cached schema contains no flags")
                return cached
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            # Cache is an optimization only. Never make it a probing dependency.
            cache_file = None

    version_output = _run(exe, "--version").strip()
    help_output = _run(exe, "--help")
    if not help_output.strip():
        raise ProbeError("Executable returned empty --help output")

    schema = parse_help(
        help_output,
        executable_type=detect_executable_type(exe),
        version=version_output or "unknown",
    )
    if not schema.flags:
        raise ProbeError("Could not parse any command-line options from --help output")

    if use_cache:
        try:
            if cache_file is None:
                root = Path(cache_dir) if cache_dir is not None else default_cache_dir()
                cache_file = root / f"{schema_cache_key(exe)}.json"
            save_schema(schema, cache_file)
        except OSError:
            pass

    return schema
