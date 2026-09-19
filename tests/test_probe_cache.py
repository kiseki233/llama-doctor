from pathlib import Path

from llama_doctor.core import executable_probe


HELP = """usage: llama-server [options]\n  -m, --model FNAME    model path\n  -c, --ctx-size N     context size\n"""


def test_probe_uses_cache(monkeypatch, tmp_path):
    exe = tmp_path / "llama-server"
    exe.write_bytes(b"fake executable bytes")
    calls = []

    def fake_run(path: Path, arg: str, timeout: float = 8.0) -> str:
        calls.append(arg)
        return "build-test" if arg == "--version" else HELP

    monkeypatch.setattr(executable_probe, "_run", fake_run)
    cache_dir = tmp_path / "cache"

    first = executable_probe.probe_executable(exe, cache_dir=cache_dir)
    assert first.version == "build-test"
    assert calls == ["--version", "--help"]

    calls.clear()
    second = executable_probe.probe_executable(exe, cache_dir=cache_dir)
    assert second.version == "build-test"
    assert calls == []


def test_corrupt_cache_falls_back_to_probe(monkeypatch, tmp_path):
    exe = tmp_path / "llama-server"
    exe.write_bytes(b"fake executable bytes")
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    key = executable_probe.schema_cache_key(exe)
    (cache_dir / f"{key}.json").write_text("not json")

    def fake_run(path: Path, arg: str, timeout: float = 8.0) -> str:
        return "build-test" if arg == "--version" else HELP

    monkeypatch.setattr(executable_probe, "_run", fake_run)
    schema = executable_probe.probe_executable(exe, cache_dir=cache_dir)
    assert schema.version == "build-test"
    assert "--model" in schema.flags


def test_old_cache_format_is_ignored(monkeypatch, tmp_path):
    exe = tmp_path / "llama-server"
    exe.write_bytes(b"fake executable bytes")
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    key = executable_probe.schema_cache_key(exe)
    (cache_dir / f"{key}.json").write_text(
        '{"cache_format": 1, "executable_type": "wrong", "version": "old", "flags": {}}'
    )

    calls = []

    def fake_run(path: Path, arg: str, timeout: float = 8.0) -> str:
        calls.append(arg)
        return "build-new" if arg == "--version" else HELP

    monkeypatch.setattr(executable_probe, "_run", fake_run)
    schema = executable_probe.probe_executable(exe, cache_dir=cache_dir)
    assert schema.version == "build-new"
    assert calls == ["--version", "--help"]


def test_structurally_valid_but_empty_cache_falls_back_to_probe(monkeypatch, tmp_path):
    exe = tmp_path / "llama-server"
    exe.write_bytes(b"fake executable bytes")
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    key = executable_probe.schema_cache_key(exe)
    (cache_dir / f"{key}.json").write_text(
        '{"cache_format": 2, "executable_type": "llama-server", "version": "bad", "raw_help": "", "flags": {}}'
    )

    calls = []

    def fake_run(path: Path, arg: str, timeout: float = 8.0) -> str:
        calls.append(arg)
        return "build-new" if arg == "--version" else HELP

    monkeypatch.setattr(executable_probe, "_run", fake_run)
    schema = executable_probe.probe_executable(exe, cache_dir=cache_dir)
    assert schema.version == "build-new"
    assert "--model" in schema.flags
    assert calls == ["--version", "--help"]


def test_previous_schema_cache_format_is_ignored_after_parser_semantics_change(monkeypatch, tmp_path):
    exe = tmp_path / "llama-server"
    exe.write_bytes(b"fake executable bytes")
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    key = executable_probe.schema_cache_key(exe)
    # Recreate the key used by format 3, then place a deliberately stale v2 payload there.
    (cache_dir / f"{key}.json").write_text(
        '{"cache_format": 2, "executable_type": "llama-server", "version": "stale", "raw_help": "", "flags": {"--ctx-size": {"name": "--ctx-size", "aliases": ["-c"], "requires_value": true, "value_optional": false, "value_name": "N", "value_type": "string", "choices": null, "min_value": null, "max_value": null, "env_var": null, "deprecated": false, "description": "size of the prompt context"}}}'
    )

    calls = []

    def fake_run(path: Path, arg: str, timeout: float = 8.0) -> str:
        calls.append(arg)
        return "build-new" if arg == "--version" else HELP

    monkeypatch.setattr(executable_probe, "_run", fake_run)
    schema = executable_probe.probe_executable(exe, cache_dir=cache_dir)
    assert schema.version == "build-new"
    assert calls == ["--version", "--help"]
