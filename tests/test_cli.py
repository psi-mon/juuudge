import pytest
from click.testing import CliRunner
from juuudge.cli import main
from juuudge.storage.db import Database
from juuudge.models import Card, Rule

def test_cli_card_and_rule_lookup(tmp_path, monkeypatch):
    monkeypatch.setenv("JUUUDGE_DIR", str(tmp_path))
    db = Database(tmp_path / "juuudge.db")
    db.init_schema()
    db.insert_cards([Card(name="Blood Moon", mana_cost="{2}{R}", type_line="Enchantment", oracle_text="Nonbasic lands are Mountains.")])
    db.insert_rules([Rule(rule_id="613.1d", chapter="6. Spells", section="613. Continuous Effects", parent_rule="613.1", text="Layer 4: Type change.")])

    runner = CliRunner()
    
    # Test card lookup
    res_card = runner.invoke(main, ["card", "Blood Moon"])
    assert res_card.exit_code == 0
    assert "Enchantment" in res_card.output
    assert "Mountains" in res_card.output

    # Test rule lookup
    res_rule = runner.invoke(main, ["rule", "613.1d"])
    assert res_rule.exit_code == 0
    assert "Layer 4: Type change" in res_rule.output
