import pytest
from click.testing import CliRunner
from unittest.mock import patch, AsyncMock
from juuudge.cli import main
from juuudge.storage.db import Database
from juuudge.config import get_config
from juuudge.tui.app import JuuudgeApp
from juuudge.tui.widgets import SetupModal

def test_cli_setup_anthropic_non_interactive(tmp_path, monkeypatch):
    monkeypatch.setenv("JUUUDGE_DIR", str(tmp_path))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    runner = CliRunner()
    result = runner.invoke(main, [
        "setup",
        "--provider", "anthropic",
        "--api-key", "sk-ant-test-secret-key-123",
        "--model", "claude-3-7-sonnet"
    ])
    assert result.exit_code == 0
    assert "Anthropic provider configured successfully" in result.output

    db = Database(tmp_path / "juuudge.db")
    db.init_schema()
    cfg = db.get_provider_config()
    assert cfg["provider"] == "anthropic"
    assert cfg["api_key"] == "sk-ant-test-secret-key-123"
    assert cfg["model"] == "claude-3-7-sonnet"
    
    # Must be encrypted in DB
    raw_key = db.get_setting("anthropic_api_key")
    assert raw_key.startswith("enc_v1:")
    assert "sk-ant-test-secret-key-123" not in raw_key

def test_cli_setup_ollama_non_interactive(tmp_path, monkeypatch):
    monkeypatch.setenv("JUUUDGE_DIR", str(tmp_path))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    runner = CliRunner()
    result = runner.invoke(main, [
        "setup",
        "--provider", "ollama",
        "--host", "http://localhost:11434",
        "--model", "llama3.3"
    ])
    assert result.exit_code == 0
    assert "Ollama provider configured successfully" in result.output

    db = Database(tmp_path / "juuudge.db")
    db.init_schema()
    cfg = db.get_provider_config()
    assert cfg["provider"] == "ollama"
    assert cfg["ollama_host"] == "http://localhost:11434"
    assert cfg["model"] == "llama3.3"

def test_cli_ask_unconfigured_error(tmp_path, monkeypatch):
    monkeypatch.setenv("JUUUDGE_DIR", str(tmp_path))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    runner = CliRunner()
    result = runner.invoke(main, ["ask", "Does Blood Moon kill Urza's Saga?"])
    assert result.exit_code == 0
    assert "Error:" in result.output
    assert "juuudge setup" in result.output

@pytest.mark.asyncio
async def test_tui_unconfigured_shows_warning(tmp_path, monkeypatch):
    monkeypatch.setenv("JUUUDGE_DIR", str(tmp_path))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    app = JuuudgeApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        inp = app.query_one("#input-box")
        inp.value = "Does Blood Moon kill Urza's Saga?"
        await inp.action_submit()
        await pilot.pause()

        # Check that error was printed and modal was shown
        assert len(app.screen_stack) > 1
        assert isinstance(app.screen_stack[-1], SetupModal)
        assert "Provider Setup Required" in "".join(app.chat_history)

def test_cli_setup_show_unconfigured(tmp_path, monkeypatch):
    monkeypatch.setenv("JUUUDGE_DIR", str(tmp_path))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    runner = CliRunner()
    result = runner.invoke(main, ["setup", "--show"])
    assert result.exit_code == 0
    assert "No provider configured yet" in result.output

def test_cli_setup_show_anthropic(tmp_path, monkeypatch):
    monkeypatch.setenv("JUUUDGE_DIR", str(tmp_path))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    runner = CliRunner()
    # Configure first
    runner.invoke(main, [
        "setup",
        "--provider", "anthropic",
        "--api-key", "sk-ant-test-super-secret-key-999",
        "--model", "claude-3-7-sonnet"
    ])

    # Now show
    result = runner.invoke(main, ["setup", "--show"])
    assert result.exit_code == 0
    assert "anthropic" in result.output
    assert "claude-3-7-sonnet" in result.output
    # Must display masked fingerprint with last 4
    assert "sk-ant-…-999" in result.output or "sk-ant-...-999" in result.output
    # Must NOT contain the full secret
    assert "sk-ant-test-super-secret-key-999" not in result.output

def test_cli_setup_show_decrypt_failed(tmp_path, monkeypatch):
    monkeypatch.setenv("JUUUDGE_DIR", str(tmp_path))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    db = Database(tmp_path / "juuudge.db")
    db.init_schema()
    # Inject an invalid/corrupted encrypted blob directly in DB
    db.set_setting("provider", "anthropic")
    db.set_setting("model", "claude-3-7-sonnet-20250219")
    db.set_setting("anthropic_api_key", "enc_v1:00112233445566778899aabbccddeeff:0102030405060708090a")
    db.set_setting("setup_completed", "true")

    runner = CliRunner()
    result = runner.invoke(main, ["setup", "--show"])
    assert result.exit_code == 0
    assert "<encrypted, decrypt failed>" in result.output
    # Must be printable and clean
    assert all(ord(c) >= 32 or c in "\n\r\t" for c in result.output)

def test_cli_setup_show_rich_escaping(tmp_path, monkeypatch):
    monkeypatch.setenv("JUUUDGE_DIR", str(tmp_path))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    # Provider with brackets or markup-like content
    db = Database(tmp_path / "juuudge.db")
    db.init_schema()
    db.set_setting("provider", "anthropic")
    db.set_setting("model", "custom[bracket]model")
    db.set_setting("setup_completed", "true")

    runner = CliRunner()
    result = runner.invoke(main, ["setup", "--show"])
    assert result.exit_code == 0
    assert "custom[bracket]model" in result.output
    assert all(ord(c) >= 32 or c in "\n\r\t" for c in result.output)

def test_cli_setup_show_ollama(tmp_path, monkeypatch):
    monkeypatch.setenv("JUUUDGE_DIR", str(tmp_path))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    runner = CliRunner()
    # Configure first
    runner.invoke(main, [
        "setup",
        "--provider", "ollama",
        "--host", "http://127.0.0.1:11434",
        "--model", "llama3.3"
    ])

    # Now show
    result = runner.invoke(main, ["setup", "--show"])
    assert result.exit_code == 0
    assert "ollama" in result.output
    assert "http://127.0.0.1:11434" in result.output
    assert "llama3.3" in result.output

def test_persistence_across_sessions_with_hostname_change(tmp_path, monkeypatch):
    import platform
    from juuudge.config import validate_provider_setup
    monkeypatch.setenv("JUUUDGE_DIR", str(tmp_path))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(platform, "node", lambda: "host-session-1-mbp.local")

    # Session 1: configure provider in DB
    db1 = Database(tmp_path / "juuudge.db")
    db1.init_schema()
    db1.save_provider_config(
        provider="anthropic",
        api_key="sk-ant-persistent-key-9999",
        model="claude-3-7-sonnet-20250219"
    )

    # Session 2: simulate restart where hostname changes (DHCP/Bonjour)
    monkeypatch.setattr(platform, "node", lambda: "host-session-2-changed.local")

    db2 = Database(tmp_path / "juuudge.db")
    db2.init_schema()
    cfg2 = get_config(db2)

    valid, msg = validate_provider_setup(cfg2, db=db2)
    assert valid is True
    assert msg == ""
    assert cfg2.llm.api_key == "sk-ant-persistent-key-9999"
    assert cfg2.llm.provider == "anthropic"
