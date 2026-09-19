from pathlib import Path

from llama_doctor.core.rules import load_conflicts, load_migrations


RULES = Path(__file__).resolve().parents[1] / "src" / "llama_doctor" / "rules"


def test_migration_rules_have_unique_ids_and_flags():
    migrations = load_migrations(RULES / "migrations.json")
    assert migrations
    ids = [rule.id for rule in migrations.values()]
    assert len(ids) == len(set(ids))
    assert len(migrations) == len(set(migrations))
    for old_flag, rule in migrations.items():
        assert old_flag.startswith("-")
        assert rule.replacement.startswith("-")
        assert isinstance(rule.safe, bool)


def test_conflict_rules_have_unique_ids_and_valid_severity():
    conflicts = load_conflicts(RULES / "conflicts.json")
    ids = [rule.id for rule in conflicts]
    assert len(ids) == len(set(ids))
    for rule in conflicts:
        assert len(rule.flags) >= 2
        assert rule.severity in {"error", "warning", "info"}
